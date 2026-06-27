"""Topology derived from proxy repositories (parent/child links)."""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import ProxyLink, Repository, Topology, TopologyNode
from ..nexus_client import NexusClient, NexusError


router = APIRouter(prefix="/api", tags=["topology"])


def _host_key(url: str) -> Tuple[str, Optional[int]]:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return (parsed.hostname or "").lower(), parsed.port


def _remote_url(repo: Repository) -> Optional[str]:
    proxy = repo.attributes.get("proxy") if isinstance(repo.attributes, dict) else None
    if isinstance(proxy, dict):
        return proxy.get("remoteUrl")
    return None


async def _fetch_node(instance) -> Tuple[TopologyNode, Optional[List[Repository]]]:
    node = TopologyNode(
        id=instance.id, name=instance.name,
        base_url=instance.base_url, tier=getattr(instance, "tier", 0) or 0,
    )
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        # status_code None == connection-level failure (timeout/refused/DNS) ==
        # genuinely down. A status code means the server ANSWERED (reachable)
        # but we couldn't list its repos — e.g. 401/403 from a wrong or
        # under-privileged account. Don't flag that node (or links into it) as
        # down; surface it as a reachable-but-warning node instead.
        if exc.status_code is None:
            node.reachable = False
            node.error = exc.message
        else:
            node.error = (
                f"도달 가능하나 저장소 조회 실패(HTTP {exc.status_code}) — "
                f"계정/권한 확인 필요"
            )
        return node, None
    return node, repos


async def _probe(url: str, timeout: float) -> bool:
    """Best-effort reachability probe of a remote URL (any HTTP reply = up)."""
    try:
        verify = get_settings().verify_tls
        async with httpx.AsyncClient(timeout=timeout, verify=verify, follow_redirects=True) as c:
            await c.get(url)
        return True
    except httpx.HTTPError:
        return False


@router.get("/topology", response_model=Topology)
async def topology(
    probe: bool = Query(False, description="Actively probe each remote URL."),
    registry: InstanceRegistry = Depends(get_registry),
) -> Topology:
    """Build the proxy topology and flag broken upstream links.

    Each proxy repository's ``remoteUrl`` becomes an edge. When the upstream
    host matches another managed node it is an internal link; a link is
    "broken" when its internal target node is unreachable (the proxy will
    auto-block). Optionally probe each remote URL directly.
    """
    instances = registry.all()
    results = await asyncio.gather(*(_fetch_node(i) for i in instances))

    # Map host:port -> node id for internal-link matching. A server may be
    # referenced by IP in one proxy and by FQDN in another, so the optional
    # alt_url is registered too (base_url keys win on collision).
    host_to_id: Dict[Tuple[str, Optional[int]], str] = {}
    for inst in instances:
        host_to_id[_host_key(inst.base_url)] = inst.id
    for inst in instances:
        if inst.alt_url:
            host_to_id.setdefault(_host_key(inst.alt_url), inst.id)
    node_reachable = {node.id: node.reachable for node, _ in results}

    nodes: List[TopologyNode] = []
    broken_total = 0
    probe_timeout = min(get_settings().request_timeout, 8.0)

    for node, repos in results:
        if repos:
            for repo in repos:
                remote = _remote_url(repo)
                if not remote:
                    continue
                key = _host_key(remote)
                # Exact host:port first; fall back to a port-less registration
                # (e.g. alt_url entered as a bare hostname).
                target_id = host_to_id.get(key) or host_to_id.get((key[0], None))
                link = ProxyLink(
                    repository=repo.name,
                    remote_url=remote,
                    target_host=f"{key[0]}:{key[1]}" if key[1] else key[0],
                    target_id=target_id,
                    internal=target_id is not None,
                )
                if target_id is not None:
                    link.remote_reachable = node_reachable.get(target_id)
                    link.broken = not node_reachable.get(target_id, False)
                node.proxies.append(link)

        nodes.append(node)

    if probe:
        # Probe every remote URL concurrently and update reachability/broken.
        all_links = [lnk for node in nodes for lnk in node.proxies]
        probes = await asyncio.gather(
            *(_probe(lnk.remote_url, probe_timeout) for lnk in all_links)
        )
        for lnk, ok in zip(all_links, probes):
            lnk.remote_reachable = ok
            if lnk.internal:
                lnk.broken = not ok

    broken_total = sum(1 for node in nodes for lnk in node.proxies if lnk.broken)
    return Topology(nodes=nodes, broken_links=broken_total)


@router.get("/proxy-status")
async def proxy_status(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Fleet-wide proxy remote-health board.

    For every monitored instance, combine the repository list (remote URLs)
    with the internal per-repo runtime status (the only API that exposes
    'Remote Auto Blocked') and classify each proxy: ok / blocked / offline.
    """
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            repos = await client.list_repositories()
        except NexusError as exc:
            return inst, None, None, exc.message
        statuses = None
        try:
            statuses = await client.repo_statuses()
        except NexusError:
            pass  # older version / no permission — degrade to unknown
        return inst, repos, statuses, None

    results = await asyncio.gather(*(one(i) for i in instances))

    items: List[dict] = []
    errors: Dict[str, str] = {}
    counts = {"ok": 0, "blocked": 0, "offline": 0, "unknown": 0}
    for inst, repos, statuses, err in results:
        if err is not None:
            errors[inst.id] = err
            continue
        smap = {}
        for s in statuses or []:
            if isinstance(s, dict) and s.get("name"):
                smap[s["name"]] = s.get("status") or {}
        for repo in repos or []:
            if (repo.type or "").lower() != "proxy":
                continue
            remote = _remote_url(repo) or ""
            st = smap.get(repo.name)
            if st is None:
                state, detail = "unknown", "상태 조회 불가"
            else:
                online = st.get("online")
                desc = st.get("description") or ""
                reason = st.get("reason") or ""
                if online is False:
                    state, detail = "offline", desc or "offline"
                elif "blocked" in desc.lower():
                    state, detail = "blocked", (f"{desc} — {reason}" if reason else desc)
                else:
                    state, detail = "ok", desc or "Ready to Connect"
            counts[state] = counts.get(state, 0) + 1
            items.append({
                "instance_id": inst.id,
                "instance_name": inst.name,
                "repository": repo.name,
                "format": repo.format,
                "remote_url": remote,
                "state": state,
                "detail": detail,
            })

    order = {"blocked": 0, "offline": 1, "unknown": 2, "ok": 3}
    items.sort(key=lambda x: (order.get(x["state"], 9), x["instance_name"], x["repository"]))
    return {"counts": counts, "items": items, "errors": errors, "scanned": len(instances)}


def _suggest(reachable: bool, elapsed_ms, auto_block: bool) -> str:
    if not reachable:
        return ("매니저에서도 원격에 연결할 수 없습니다 — 네트워크/방화벽 차단 또는 원격 다운. "
                "경로 개통(또는 원격 복구) 후 '차단 초기화'를 누르세요.")
    if elapsed_ms is not None and elapsed_ms > 5000:
        return ("원격이 매우 느립니다 — 기본 타임아웃(20초×3회) 안에 응답하지 못해 차단됐을 수 있습니다. "
                "'타임아웃 60초로 상향'을 권장합니다.")
    return ("매니저에서는 원격이 정상입니다 — 해당 Nexus 서버↔원격 구간 문제였거나 일시 장애입니다. "
            "'차단 초기화'로 즉시 재시도시키세요." + ("" if auto_block else " (auto-block은 이미 꺼져 있음)"))


@router.get("/proxy-status/diagnose")
async def proxy_diagnose(
    instance_id: str = Query(...),
    repository: str = Query(...),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Diagnose a blocked proxy: probe its remote from the manager and report
    the repo's timeout/retry/auto-block settings with a suggested fix."""
    import time as _time

    inst = registry.get(instance_id)
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        return {"error": f"저장소 조회 실패: {exc.message}"}
    repo = next((r for r in repos if r.name == repository), None)
    if repo is None:
        return {"error": f"'{repository}' 저장소가 없습니다."}
    remote = _remote_url(repo) or ""

    cfg = {}
    try:
        cfg = await client.get_repository_config(repo.format, repo.type, repository)
    except NexusError:
        pass
    http = cfg.get("httpClient") or {}
    conn = http.get("connection") or {}

    reachable = False
    status_code = None
    elapsed_ms = None
    err = ""
    if remote:
        start = _time.perf_counter()
        try:
            verify = get_settings().verify_tls
            async with httpx.AsyncClient(timeout=10.0, verify=verify, follow_redirects=True) as c:
                resp = await c.get(remote)
            status_code = resp.status_code
            reachable = True
        except httpx.HTTPError as exc:
            err = str(exc).strip() or type(exc).__name__
        elapsed_ms = round((_time.perf_counter() - start) * 1000)

    auto_block = bool(http.get("autoBlock", True))
    return {
        "remote_url": remote,
        "reachable": reachable,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "probe_error": err,
        "timeout": conn.get("timeout"),
        "retries": conn.get("retries"),
        "auto_block": auto_block,
        "blocked": bool(http.get("blocked", False)),
        "suggestion": _suggest(reachable, elapsed_ms, auto_block),
        "note": "※ 이 점검은 매니저 서버 기준입니다. 해당 Nexus 서버에서의 도달성은 다를 수 있습니다.",
    }


@router.post("/proxy-status/fix")
async def proxy_fix(
    instance_id: str = Query(...),
    repository: str = Query(...),
    action: str = Query(..., pattern="^(reset|timeout|autoblock_off)$"),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Apply a fix to a blocked proxy.

    * ``reset`` — re-save the config unchanged, which resets the proxy facet
      and clears the auto-block so Nexus retries the remote immediately.
    * ``timeout`` — raise request timeout to 60s with 3 retries (community
      recommendation for slow remotes).
    * ``autoblock_off`` — disable auto-block for this repository.
    """
    inst = registry.get(instance_id)
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"저장소 조회 실패: {exc.message}")
    repo = next((r for r in repos if r.name == repository), None)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"'{repository}' 저장소가 없습니다.")
    try:
        cfg = await client.get_repository_config(repo.format, repo.type, repository)
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"설정 읽기 실패(권한 등): {exc.message}")

    payload = {k: v for k, v in cfg.items() if k not in ("format", "type", "url")}
    http = dict(payload.get("httpClient") or {"blocked": False, "autoBlock": True})
    if action == "timeout":
        conn = dict(http.get("connection") or {})
        conn["timeout"] = 60
        conn["retries"] = 3
        http["connection"] = conn
        detail = "Request Timeout 60초 / 재시도 3회로 상향"
    elif action == "autoblock_off":
        http["autoBlock"] = False
        detail = "auto-block 해제됨 (원격 장애 시 요청이 길게 대기할 수 있음)"
    else:
        detail = "설정 재저장으로 차단 초기화 — Nexus가 원격을 즉시 재시도합니다"
    payload["httpClient"] = http

    try:
        await client.update_repository(repo.format, repo.type, repository, payload)
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"설정 변경 실패: {exc.message}")
    return {"ok": True, "action": action, "detail": detail}


@router.post("/proxy-status/fix-all")
async def proxy_fix_all(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Reset (clear auto-block) on EVERY currently-blocked proxy, fleet-wide.

    Re-saves each blocked proxy's config unchanged so Nexus retries the remote
    immediately. Use after the upstream/path is restored.
    """
    async def one(inst) -> dict:
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            repos = await client.list_repositories()
        except NexusError as exc:
            return {"instance_id": inst.id, "instance_name": inst.name,
                    "error": exc.message, "reset": [], "failed": []}
        try:
            statuses = await client.repo_statuses()
        except NexusError as exc:
            return {"instance_id": inst.id, "instance_name": inst.name,
                    "error": f"상태 조회 불가: {exc.message}", "reset": [], "failed": []}
        smap = {s["name"]: (s.get("status") or {})
                for s in (statuses or []) if isinstance(s, dict) and s.get("name")}
        blocked = [
            r for r in repos
            if (r.type or "").lower() == "proxy"
            and "blocked" in str(smap.get(r.name, {}).get("description", "")).lower()
        ]
        reset: List[str] = []
        failed: List[dict] = []
        for r in blocked:
            try:
                cfg = await client.get_repository_config(r.format, r.type, r.name)
                payload = {k: v for k, v in cfg.items() if k not in ("format", "type", "url")}
                payload["httpClient"] = dict(payload.get("httpClient") or {"blocked": False, "autoBlock": True})
                await client.update_repository(r.format, r.type, r.name, payload)
                reset.append(r.name)
            except NexusError as exc:
                failed.append({"repository": r.name, "error": exc.message})
        return {"instance_id": inst.id, "instance_name": inst.name,
                "reset": reset, "failed": failed}

    results = list(await asyncio.gather(*(one(i) for i in registry.monitoring())))
    return {
        "reset": sum(len(r["reset"]) for r in results),
        "failed": sum(len(r.get("failed", [])) for r in results),
        "by_instance": results,
    }
