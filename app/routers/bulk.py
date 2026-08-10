"""Bulk repository-config editing: read every repo's settings on one
instance, group them by field, and apply one value to all repos at once
(e.g. turn httpClient.autoBlock off everywhere)."""

import asyncio
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/bulk", tags=["bulk"])

# Identity/section keys that must never be bulk-edited.
_PROTECTED = ("name", "format", "type", "url")


def _flatten(prefix: str, obj: dict, out: Dict[str, Any]) -> None:
    """Flatten nested dicts to dotted keys; lists/scalars are leaves."""
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            _flatten(key, v, out)
        else:
            out[key] = v


@router.get("/fields")
async def bulk_fields(
    instance_id: str = Query(...),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Read every repository's config on the instance and group by field.

    Returns each dotted field with how many repos carry it and the observed
    value distribution, so the UI can offer a sensible bulk editor.
    """
    inst = registry.get(instance_id)  # 404 if unknown
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"저장소 조회 실패: {exc.message}")

    async def one(r):
        try:
            cfg = await client.get_repository_config(r.format, r.type, r.name)
            return r, cfg, None
        except NexusError as exc:
            return r, None, exc.message

    results = await asyncio.gather(*(one(r) for r in repos))

    fields: Dict[str, dict] = {}
    errors: Dict[str, str] = {}
    loaded = 0
    for r, cfg, err in results:
        if err is not None or not isinstance(cfg, dict):
            errors[r.name] = err or "설정 형식 오류"
            continue
        loaded += 1
        flat: Dict[str, Any] = {}
        _flatten("", {k: v for k, v in cfg.items() if k not in _PROTECTED}, flat)
        for k, v in flat.items():
            f = fields.setdefault(
                k, {"key": k, "repos": 0, "values": {}, "all_bool": True}
            )
            f["repos"] += 1
            disp = json.dumps(v, ensure_ascii=False)
            f["values"][disp] = f["values"].get(disp, 0) + 1
            if not isinstance(v, bool):
                f["all_bool"] = False

    return {
        "instance": inst.id,
        "repos": len(repos),
        "loaded": loaded,
        "errors": errors,
        "fields": sorted(fields.values(), key=lambda f: f["key"]),
    }


class BulkApplyBody(BaseModel):
    instance_id: str
    key: str
    value: Any = None


@router.post("/apply")
async def bulk_apply(
    body: BulkApplyBody,
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Set one config field to the given value on every repo that has it.

    A repo is skipped when its config lacks the field's top-level section
    (e.g. ``httpClient`` on a hosted repo) or already holds the same value;
    deeper intermediate objects are created as needed (e.g.
    ``httpClient.connection.timeout``).
    """
    key = (body.key or "").strip()
    segs = [s for s in key.split(".") if s]
    if not segs or segs[0] in _PROTECTED:
        raise HTTPException(status_code=400, detail=f"이 항목은 일괄 변경할 수 없습니다: {key!r}")

    inst = registry.get(body.instance_id)  # 404 if unknown
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"저장소 조회 실패: {exc.message}")

    async def one(r) -> dict:
        try:
            cfg = await client.get_repository_config(r.format, r.type, r.name)
        except NexusError as exc:
            return {"repository": r.name, "status": "fail",
                    "detail": f"설정 읽기 실패: {exc.message}"}
        if not isinstance(cfg, dict) or segs[0] not in cfg:
            return {"repository": r.name, "status": "skip", "detail": "해당 설정 없음"}
        payload = {k: v for k, v in cfg.items() if k not in ("format", "type", "url")}
        cur = payload
        for s in segs[:-1]:
            nxt = cur.get(s)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[s] = nxt
            cur = nxt
        old = cur.get(segs[-1])
        if type(old) is type(body.value) and old == body.value:
            return {"repository": r.name, "status": "skip", "detail": "이미 같은 값"}
        cur[segs[-1]] = body.value
        try:
            await client.update_repository(r.format, r.type, r.name, payload)
        except NexusError as exc:
            return {"repository": r.name, "status": "fail", "detail": exc.message}
        return {"repository": r.name, "status": "ok", "detail": ""}

    items: List[dict] = list(await asyncio.gather(*(one(r) for r in repos)))
    counts = {"ok": 0, "skip": 0, "fail": 0}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    order = {"fail": 0, "ok": 1, "skip": 2}
    items.sort(key=lambda x: (order.get(x["status"], 9), x["repository"]))
    return {"key": key, "value": body.value, "counts": counts, "items": items}
