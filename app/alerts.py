"""Threshold alerting: periodic checks + Slack-compatible webhook push.

Evaluates node-down, heap and disk thresholds across monitoring-enabled
instances. Alerts fire on transition (not every poll) and resolve when the
condition clears. The current set is also exposed via /api/alerts so the
dashboard can show it even when no webhook is configured.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List

import httpx

from .config import Settings, get_settings
from .models import Alert
from .routers.monitoring import _blobstores_for, _metrics_for, _status_for


async def _current_alerts(registry, settings: Settings) -> List[Alert]:
    nodes = registry.monitoring()
    if not nodes:
        return []
    statuses, metrics, blobs = await asyncio.gather(
        asyncio.gather(*(_status_for(i) for i in nodes)),
        asyncio.gather(*(_metrics_for(i) for i in nodes)),
        asyncio.gather(*(_blobstores_for(i) for i in nodes)),
    )

    alerts: List[Alert] = []
    for s in statuses:
        if not s.reachable:
            alerts.append(Alert(
                key=f"down:{s.id}", severity="critical", node=s.name,
                message=f"{s.name} 연결 불가: {s.error or ''}".strip(),
            ))
    for m in metrics:
        if m.reachable and m.heap_usage_pct is not None and m.heap_usage_pct >= settings.alert_heap_pct:
            alerts.append(Alert(
                key=f"heap:{m.id}", severity="warning", node=m.name,
                message=f"{m.name} Heap 사용률 {m.heap_usage_pct}%",
            ))
    for b in blobs:
        if not b.reachable:
            continue
        for store in b.blobstores:
            used, avail = store.total_size_bytes, store.available_space_bytes
            if used is None or avail is None:
                continue
            total = used + avail
            pct = (used / total * 100) if total > 0 else 0
            if pct >= settings.alert_disk_pct:
                alerts.append(Alert(
                    key=f"disk:{b.id}:{store.name}", severity="warning", node=b.name,
                    message=f"{b.name} / {store.name} 디스크 사용률 {pct:.0f}%",
                ))

    if settings.alert_drift:
        alerts.extend(await _drift_alerts(registry, settings))
    return alerts


async def _drift_alerts(registry, settings: Settings) -> List[Alert]:
    """Alert when a repository's configuration drifts across instances."""
    from .matrix import build_matrix
    from .models import MatrixColumn
    from .nexus_client import NexusClient, NexusError

    nodes = [i for i in registry.comparison()]
    if len(nodes) < 2:
        return []

    async def fetch(inst):
        col = MatrixColumn(id=inst.id, name=inst.name)
        client = NexusClient(inst, timeout=settings.request_timeout)
        try:
            repos = await client.list_repositories()
        except NexusError as exc:
            col.reachable = False
            col.error = exc.message
            return col, None
        return col, repos

    results = await asyncio.gather(*(fetch(i) for i in nodes))
    columns = [c for c, _ in results]
    repos_by_instance = {c.id: r for c, r in results}
    matrix = build_matrix(columns, repos_by_instance)

    out: List[Alert] = []
    for row in matrix.rows:
        if row.status == "drift":
            out.append(Alert(
                key=f"drift:{row.repository}", severity="warning", node="비교",
                message=f"구성 드리프트: 저장소 '{row.repository}' 설정이 서버 간 상이",
            ))
    return out


async def _send(webhook: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            await client.post(webhook, json={"text": text})
    except httpx.HTTPError:
        pass  # never let notification failure break the loop


class AlertManager:
    def __init__(self) -> None:
        self.alerts: List[Alert] = []
        self._prev_keys: set[str] = set()

    async def evaluate(self, registry, settings: Settings) -> List[Alert]:
        current = await _current_alerts(registry, settings)
        by_key: Dict[str, Alert] = {a.key: a for a in current}
        keys = set(by_key)
        if settings.alert_webhook:
            for key in keys - self._prev_keys:
                a = by_key[key]
                icon = "🔴" if a.severity == "critical" else "🟠"
                await _send(settings.alert_webhook, f"{icon} [발생] {a.message}")
            for key in self._prev_keys - keys:
                await _send(settings.alert_webhook, f"✅ [해제] {key}")
        self._prev_keys = keys
        self.alerts = current
        return current


manager = AlertManager()


async def run_loop() -> None:
    """Background polling loop, launched at app startup."""
    from .deps import registry

    while True:
        settings = get_settings()
        try:
            if registry.all():
                await manager.evaluate(registry, settings)
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(max(10.0, settings.alert_interval))
