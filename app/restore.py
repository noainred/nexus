"""Restore a Nexus configuration from a snapshot produced by the
``/config-export`` endpoint.

This recreates *configuration* (not artifact data) on a target server via the
REST API: blob stores, cleanup/routing policies, content selectors, privileges,
roles, users and repositories. It is intentionally:

* **idempotent** — items that already exist are skipped, not overwritten, so a
  restore can be re-run safely;
* **best-effort** — every item is attempted independently and failures are
  reported per item instead of aborting the whole restore;
* **dependency-ordered** — blob stores and policies are created before the
  repositories that reference them; content selectors/privileges before roles
  before users.

Known limits (reported to the caller): proxy/user passwords are never present in
a snapshot (Nexus redacts them), so restored users get a temporary password and
restored proxy repositories may need their remote credentials re-entered. Tasks
and externally-sourced (LDAP/SAML) users/roles are not recreated.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional, Set

from .nexus_client import NexusClient, NexusError

# All sections this module knows how to restore, in dependency order.
ALL_SECTIONS = [
    "blobStores",
    "cleanupPolicies",
    "routingRules",
    "contentSelectors",
    "privileges",
    "roles",
    "users",
    "repositories",
    "anonymous",
]

# Repositories must be created in this order (groups reference members).
_TYPE_RANK = {"hosted": 0, "proxy": 1, "group": 2}


def _new_temp_password() -> str:
    return "Nx-" + secrets.token_urlsafe(12) + "!9"


class _Report:
    def __init__(self) -> None:
        self.items: List[Dict[str, str]] = []

    def add(self, section: str, item: str, status: str, detail: str = "") -> None:
        self.items.append(
            {"section": section, "item": item, "status": status, "detail": detail}
        )

    def summary(self) -> Dict[str, int]:
        out = {"ok": 0, "skip": 0, "fail": 0}
        for it in self.items:
            out[it["status"]] = out.get(it["status"], 0) + 1
        return out


async def apply(
    client: NexusClient,
    snapshot: Dict[str, Any],
    sections: Optional[Set[str]] = None,
    mode: str = "merge",
) -> Dict[str, Any]:
    """Apply ``snapshot`` to the server behind ``client``.

    ``sections`` optionally restricts which sections are restored; ``None``
    means every supported section present in the snapshot.

    ``mode`` controls how existing items are handled:
      * ``"merge"`` (default) — keep existing items, only create missing ones;
      * ``"overwrite"`` — update existing items (PUT) to match the snapshot and
        create missing ones. Blob stores are never overwritten (path changes
        could detach stored data), only created when missing.
    """
    data = snapshot.get("sections") if isinstance(snapshot, dict) else None
    if not isinstance(data, dict):
        return {"items": [], "summary": {"ok": 0, "skip": 0, "fail": 0},
                "error": "스냅샷 형식이 올바르지 않습니다 (sections 없음)."}

    overwrite = mode == "overwrite"
    want = set(sections) if sections else set(ALL_SECTIONS)
    rep = _Report()
    temp_password: Optional[str] = None

    if "blobStores" in want:
        await _restore_blobstores(client, data.get("blobStores"), rep)
    if "cleanupPolicies" in want:
        await _restore_cleanup(client, data.get("cleanupPolicies"), rep)
    if "routingRules" in want:
        await _restore_routing(client, data.get("routingRules"), rep, overwrite)
    if "contentSelectors" in want:
        await _restore_content_selectors(client, data.get("contentSelectors"), rep, overwrite)
    if "privileges" in want:
        await _restore_privileges(client, data.get("privileges"), rep, overwrite)
    if "roles" in want:
        await _restore_roles(client, data.get("roles"), rep, overwrite)
    if "users" in want:
        temp_password = await _restore_users(client, data.get("users"), rep, overwrite)
    if "repositories" in want:
        await _restore_repositories(client, data.get("repositories"), rep, overwrite)
    if "anonymous" in want:
        await _restore_anonymous(client, data.get("anonymous"), rep)

    out: Dict[str, Any] = {"items": rep.items, "summary": rep.summary(), "mode": mode}
    if temp_password:
        out["tempPassword"] = temp_password
    return out


async def _restore_blobstores(client, items, rep: _Report) -> None:
    if not isinstance(items, list):
        return
    existing = await client.existing_names("/blobstores")
    for bs in items:
        if not isinstance(bs, dict):
            continue
        name = bs.get("name")
        btype = (bs.get("type") or "").lower()
        if btype != "file":
            rep.add("blobStores", str(name), "skip",
                    f"{bs.get('type')} 타입은 자동 복구 미지원(서버에서 직접 생성)")
            continue
        if name in existing:
            rep.add("blobStores", str(name), "skip", "이미 존재")
            continue
        detail = bs.get("detail") if isinstance(bs.get("detail"), dict) else {}
        path = detail.get("path") or name
        payload: Dict[str, Any] = {"name": name, "path": path}
        if detail.get("softQuota"):
            payload["softQuota"] = detail["softQuota"]
        try:
            await client.create_blobstore_file(payload)
            rep.add("blobStores", str(name), "ok", f"path={path}")
        except NexusError as exc:
            rep.add("blobStores", str(name), "fail", exc.message)


async def _restore_cleanup(client, items, rep: _Report) -> None:
    if not isinstance(items, list):
        return
    try:
        existing = {p.name for p in await client.list_cleanup_policies()}
    except NexusError:
        existing = set()
    for pol in items:
        if not isinstance(pol, dict):
            continue
        name = pol.get("name")
        if name in existing:
            rep.add("cleanupPolicies", str(name), "skip", "이미 존재")
            continue
        payload = {k: pol.get(k) for k in ("name", "format", "notes", "mode", "criteria")
                   if pol.get(k) is not None}
        try:
            await client.create_cleanup_policy(payload)
            rep.add("cleanupPolicies", str(name), "ok")
        except NexusError as exc:
            rep.add("cleanupPolicies", str(name), "fail", exc.message)


async def _restore_routing(client, items, rep: _Report, overwrite: bool = False) -> None:
    if not isinstance(items, list):
        return
    existing = await client.existing_names("/routing-rules")
    for rule in items:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name")
        payload = {k: rule.get(k) for k in ("name", "description", "mode", "matchers")
                   if rule.get(k) is not None}
        if name in existing:
            if not overwrite:
                rep.add("routingRules", str(name), "skip", "이미 존재")
                continue
            try:
                await client.update_routing_rule(name, payload)
                rep.add("routingRules", str(name), "update", "덮어씀")
            except NexusError as exc:
                rep.add("routingRules", str(name), "fail", exc.message)
            continue
        try:
            await client.create_routing_rule(payload)
            rep.add("routingRules", str(name), "ok")
        except NexusError as exc:
            rep.add("routingRules", str(name), "fail", exc.message)


async def _restore_content_selectors(client, items, rep: _Report, overwrite: bool = False) -> None:
    if not isinstance(items, list):
        return
    existing = await client.existing_names("/security/content-selectors")
    for cs in items:
        if not isinstance(cs, dict):
            continue
        name = cs.get("name")
        payload = {
            "name": name,
            "description": cs.get("description", ""),
            "expression": cs.get("expression", ""),
        }
        if name in existing:
            if not overwrite:
                rep.add("contentSelectors", str(name), "skip", "이미 존재")
                continue
            try:
                await client.update_content_selector(name, payload)
                rep.add("contentSelectors", str(name), "update", "덮어씀")
            except NexusError as exc:
                rep.add("contentSelectors", str(name), "fail", exc.message)
            continue
        try:
            await client.create_content_selector(payload)
            rep.add("contentSelectors", str(name), "ok")
        except NexusError as exc:
            rep.add("contentSelectors", str(name), "fail", exc.message)


async def _restore_privileges(client, items, rep: _Report, overwrite: bool = False) -> None:
    if not isinstance(items, list):
        return
    existing = await client.existing_names("/security/privileges")
    for pv in items:
        if not isinstance(pv, dict):
            continue
        name = pv.get("name")
        if pv.get("readOnly"):
            continue  # built-in privilege
        ptype = pv.get("type")
        if not ptype:
            rep.add("privileges", str(name), "skip", "type 정보 없음")
            continue
        payload = {k: v for k, v in pv.items() if k not in ("type", "readOnly")}
        if name in existing:
            if not overwrite:
                rep.add("privileges", str(name), "skip", "이미 존재")
                continue
            try:
                await client.update_privilege(ptype, name, payload)
                rep.add("privileges", str(name), "update", f"덮어씀 · type={ptype}")
            except NexusError as exc:
                rep.add("privileges", str(name), "fail", exc.message)
            continue
        try:
            await client.create_privilege(ptype, payload)
            rep.add("privileges", str(name), "ok", f"type={ptype}")
        except NexusError as exc:
            rep.add("privileges", str(name), "fail", exc.message)


async def _restore_roles(client, items, rep: _Report, overwrite: bool = False) -> None:
    if not isinstance(items, list):
        return
    existing = await client.existing_names("/security/roles", key="id")
    for role in items:
        if not isinstance(role, dict):
            continue
        rid = role.get("id")
        if role.get("readOnly"):
            continue  # built-in role
        payload = {
            "id": rid,
            "name": role.get("name", rid),
            "description": role.get("description", ""),
            "privileges": role.get("privileges", []),
            "roles": role.get("roles", []),
        }
        if rid in existing:
            if not overwrite:
                rep.add("roles", str(rid), "skip", "이미 존재")
                continue
            try:
                await client.update_role(rid, payload)
                rep.add("roles", str(rid), "update", "덮어씀")
            except NexusError as exc:
                rep.add("roles", str(rid), "fail", exc.message)
            continue
        try:
            await client.create_role(payload)
            rep.add("roles", str(rid), "ok")
        except NexusError as exc:
            rep.add("roles", str(rid), "fail", exc.message)


async def _restore_users(client, items, rep: _Report, overwrite: bool = False) -> Optional[str]:
    if not isinstance(items, list):
        return None
    try:
        existing = {u.get("userId") for u in await client.list_users()}
    except NexusError:
        existing = set()
    temp = _new_temp_password()
    created_any = False
    for user in items:
        if not isinstance(user, dict):
            continue
        uid = user.get("userId")
        source = (user.get("source") or "default").lower()
        if source not in ("default", "local"):
            rep.add("users", str(uid), "skip", f"외부 소스({user.get('source')})는 복구 제외")
            continue
        base = {
            "userId": uid,
            "firstName": user.get("firstName", ""),
            "lastName": user.get("lastName", ""),
            "emailAddress": user.get("emailAddress", ""),
            "status": user.get("status", "active"),
            "roles": user.get("roles", []),
        }
        if uid in existing:
            if not overwrite:
                rep.add("users", str(uid), "skip", "이미 존재")
                continue
            # Update keeps the existing password (not in the snapshot).
            update_payload = dict(base, source=user.get("source", "default"))
            try:
                await client.update_user(uid, update_payload)
                rep.add("users", str(uid), "update", "덮어씀(비밀번호 유지)")
            except NexusError as exc:
                rep.add("users", str(uid), "fail", exc.message)
            continue
        try:
            await client.create_user(dict(base, password=temp))
            created_any = True
            rep.add("users", str(uid), "ok", "임시 비밀번호로 생성됨")
        except NexusError as exc:
            rep.add("users", str(uid), "fail", exc.message)
    return temp if created_any else None


def _repo_sort_key(entry: Dict[str, Any]):
    return _TYPE_RANK.get((entry.get("type") or "").lower(), 1)


async def _restore_repositories(client, items, rep: _Report, overwrite: bool = False) -> None:
    if not isinstance(items, list):
        return
    try:
        existing = {r.name for r in await client.list_repositories()}
    except NexusError:
        existing = set()
    for entry in sorted([e for e in items if isinstance(e, dict)], key=_repo_sort_key):
        name = entry.get("name")
        fmt = (entry.get("format") or "").strip()
        type_ = (entry.get("type") or "").strip()
        config = entry.get("config")
        if not (fmt and type_ and isinstance(config, dict)):
            if name in existing and not overwrite:
                rep.add("repositories", str(name), "skip", "이미 존재")
            else:
                rep.add("repositories", str(name), "fail",
                        "전체 설정(config) 누락 — 복구 불가")
            continue
        # The POST/PUT body is the GET config minus read-only/derived fields.
        payload = {k: v for k, v in config.items()
                   if k not in ("format", "type", "url")}
        note = ""
        if (payload.get("proxy") or {}).get("remoteUrl") and \
                not (payload.get("httpClient") or {}).get("authentication"):
            note = "프록시 인증정보는 스냅샷에 없음 → 필요 시 재입력"
        if name in existing:
            if not overwrite:
                rep.add("repositories", str(name), "skip", "이미 존재")
                continue
            try:
                await client.update_repository(fmt, type_, name, payload)
                rep.add("repositories", str(name), "update",
                        note or f"덮어씀 · {fmt}/{type_}")
            except NexusError as exc:
                rep.add("repositories", str(name), "fail", exc.message)
            continue
        try:
            await client.create_repository(fmt, type_, payload)
            rep.add("repositories", str(name), "ok", note or f"{fmt}/{type_}")
        except NexusError as exc:
            rep.add("repositories", str(name), "fail", exc.message)


async def _restore_anonymous(client, anon, rep: _Report) -> None:
    if not isinstance(anon, dict):
        return
    payload = {k: anon.get(k) for k in ("enabled", "userId", "realmName")
               if anon.get(k) is not None}
    try:
        await client._request("PUT", "/security/anonymous", json=payload)
        rep.add("anonymous", "anonymous", "ok",
                f"enabled={payload.get('enabled')}")
    except NexusError as exc:
        rep.add("anonymous", "anonymous", "fail", exc.message)
