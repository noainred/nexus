"""Topology derived from proxy repositories (parent/child links)."""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Query

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
    node = TopologyNode(id=instance.id, name=instance.name, base_url=instance.base_url)
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        node.reachable = False
        node.error = exc.message
        return node, None
    return node, repos


async def _probe(url: str, timeout: float) -> bool:
    """Best-effort reachability probe of a remote URL (any HTTP reply = up)."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as c:
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

    # Map host:port -> node id for internal-link matching.
    host_to_id: Dict[Tuple[str, Optional[int]], str] = {}
    for inst in instances:
        host_to_id[_host_key(inst.base_url)] = inst.id
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
                target_id = host_to_id.get(key)
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
