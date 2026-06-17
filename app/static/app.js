"use strict";

const state = {
  instances: [],
  current: null,
  componentToken: null,
  componentRepo: null,
  matrix: null,
  matrixReference: "",
  repoDiff: null,
  compareDiff: null,
  downloadsLoaded: false,
  tasksLoaded: false,
  securityLoaded: false,
  contentSetup: false,
  contentMatrix: null,
  topologyLoaded: false,
  downloadSummary: null,
  dlRunId: 0,
  releaseNotes: null,
  groupOrder: [],
};

// ---- helpers -------------------------------------------------------------

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (res.status === 401) {
    // Only the manager's own auth gate sets auth_required. A 401 WITHOUT it
    // is an upstream Nexus error (a managed instance with bad credentials) and
    // must NOT pop the login overlay.
    if (body && body.auth_required) showLoginOverlay();
    throw new Error(formatApiError(body.detail, res.status));
  }
  if (!res.ok) {
    throw new Error(formatApiError(body.detail, res.status));
  }
  return body;
}

// ---- manager login ---------------------------------------------------------

// Tabs visible without login (status/monitoring). Everything else needs auth
// and is hidden in public mode — mirrors the server's public-read allowlist.
const PUBLIC_TABS = new Set([
  "overview", "instances-status", "blobstore", "metrics",
  "infra", "topology", "alerts", "about",
]);

function showLoginOverlay() {
  const ov = document.getElementById("login-overlay");
  if (ov) ov.classList.remove("hidden");
}

function hideLoginOverlay() {
  const ov = document.getElementById("login-overlay");
  if (ov) ov.classList.add("hidden");
}

// Public (not-logged-in) mode: show only status tabs + a 로그인 button; the
// protected tabs/loaders are hidden so no protected endpoint is hit.
function enterPublicMode() {
  state.publicMode = true;
  document.querySelectorAll(".tab").forEach((t) => {
    if (!PUBLIC_TABS.has(t.dataset.tab)) t.classList.add("hidden");
  });
  const lb = document.getElementById("login-btn");
  if (lb) lb.classList.remove("hidden");
  // If the saved hash points at a now-hidden tab, fall back to the overview.
  const cur = (location.hash || "").replace(/^#/, "");
  if (cur && !PUBLIC_TABS.has(cur)) history.replaceState(null, "", "#overview");
}

function setupAuth() {
  const form = document.getElementById("login-form");
  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const status = document.getElementById("login-status");
      try {
        await api("/api/login", {
          method: "POST",
          body: JSON.stringify({ password: document.getElementById("login-pw").value }),
        });
        // Full page refresh so the whole UI re-initialises with authenticated
        // data. (Revealing tabs in place left protected screens like 서버 설정
        // showing stale public-mode state because /api/instances wasn't loaded.)
        hideLoginOverlay();
        window.location.reload();
      } catch (e) {
        status.textContent = e.message;
      }
    });
  }
  const out = document.getElementById("logout-btn");
  if (out) {
    out.addEventListener("click", async () => {
      try { await api("/api/logout", { method: "POST" }); } catch (e) { /* ignore */ }
      location.reload();
    });
  }
  const inb = document.getElementById("login-btn");
  if (inb) inb.addEventListener("click", showLoginOverlay);
  const close = document.getElementById("login-close");
  if (close) close.addEventListener("click", hideLoginOverlay);
  const audit = document.getElementById("audit-refresh");
  if (audit) audit.addEventListener("click", loadAudit);
}

async function loadAudit() {
  const table = document.getElementById("audit-table");
  table.innerHTML = "";
  let items;
  try {
    items = await api("/api/audit?limit=200");
  } catch (e) {
    table.append(el("div", { class: "empty" }, `조회 실패: ${e.message}`));
    return;
  }
  if (!items.length) {
    table.append(el("div", { class: "empty" }, "기록이 없습니다."));
    return;
  }
  const rows = items.map((a) => el("tr", {}, [
    el("td", {}, a.ts || ""),
    el("td", {}, a.ip || ""),
    el("td", {}, a.method || ""),
    el("td", { class: "url" }, `${a.path}${a.query ? `?${a.query}` : ""}`),
    el("td", { class: "num" }, String(a.status ?? "")),
  ]));
  table.append(buildTable(["시각(UTC)", "IP", "메서드", "경로", "결과"], rows));
}

// FastAPI returns `detail` as a string (HTTPException) or a list of
// validation-error objects (422). Turn either into a readable message so
// toasts never show "[object Object]".
function formatApiError(detail, status) {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((e) => {
      const loc = Array.isArray(e.loc) ? e.loc.filter((x) => x !== "body").join(".") : "";
      const msg = e.msg || (typeof e === "string" ? e : JSON.stringify(e));
      return loc ? `${loc}: ${msg}` : msg;
    });
    if (parts.length) return parts.join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }
  return `요청 실패 (${status})`;
}

function toast(message, kind = "ok") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast ${kind}`;
  setTimeout(() => el.classList.add("hidden"), 3500);
}

function fmtBytes(n) {
  if (n === null || n === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString();
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  });
  return node;
}

// ---- tabs ----------------------------------------------------------------

// Activate a tab by name + run its lazy loader. Shared by clicks, the URL
// hash (so a page refresh stays on the same screen), and back/forward.
function selectTab(name) {
  const tab = document.querySelector(`.tab[data-tab="${name}"]`);
  const panel = document.getElementById(name);
  if (!tab || !panel) return false;
  // In public mode, protected tabs prompt for login instead of switching.
  if (state.publicMode && !PUBLIC_TABS.has(name)) { showLoginOverlay(); return false; }
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  tab.classList.add("active");
  panel.classList.add("active");
  // Lazy-load tabs that need it (downloads is started manually via 시작).
  if (name === "tasks" && !state.tasksLoaded) { state.tasksLoaded = true; loadTasks(); }
  if (name === "security" && !state.securityLoaded) { state.securityLoaded = true; loadSecurity(); }
  if (name === "alerts") loadAlerts();
  if (name === "content" && !state.contentSetup) { state.contentSetup = true; setupContent(); }
  if (name === "settings") { loadSettings(); loadUpdateStatus(); fillAcctInstances(); }
  if (name === "topology" && !state.topologyLoaded) { state.topologyLoaded = true; loadTopology(); }
  if (name === "blobstore") { loadBlobstores(); loadDiskCharts(); }
  if (name === "cleanup-candidates") fillCleanupInstances();
  if (name === "metrics") loadMetrics();
  if (name === "infra") loadInfra();
  if (name === "overview") loadOverviewTree();
  if (name === "instances-status") loadOverview();
  if (name === "bulk") fillBulkInstances();
  if (name === "about") renderHistory();
  return true;
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const name = tab.dataset.tab;
    if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
    selectTab(name);
  });
});

window.addEventListener("hashchange", () => {
  const name = (location.hash || "").replace(/^#/, "");
  if (name) selectTab(name);
});

// On load, restore the tab from the URL hash so refresh keeps the screen.
function restoreActiveTab() {
  const name = (location.hash || "").replace(/^#/, "");
  if (name) selectTab(name);
}

// ---- proxy remote-status board --------------------------------------------

async function fixAllBlockedProxies() {
  if (!confirm("차단(Remote Auto Blocked)된 모든 프록시를 한 번에 차단 초기화합니다.\n원격/네트워크 경로가 복구된 뒤에 사용하세요. 진행할까요?")) return;
  const summary = document.getElementById("pxs-summary");
  summary.textContent = "차단된 프록시 일괄 초기화 중…";
  try {
    const r = await api("/api/proxy-status/fix-all", { method: "POST" });
    toast(`차단 초기화 — 성공 ${r.reset || 0} · 실패 ${r.failed || 0}`, r.failed ? "err" : "ok");
  } catch (e) {
    toast(`일괄 초기화 실패: ${e.message}`, "err");
  }
  loadProxyStatus();
}

async function loadProxyStatus() {
  const table = document.getElementById("pxs-table");
  const summary = document.getElementById("pxs-summary");
  table.innerHTML = "";
  summary.textContent = "전 서버 프록시 상태 조회 중…";
  let r;
  try {
    r = await api("/api/proxy-status");
  } catch (e) {
    summary.textContent = `조회 실패: ${e.message}`;
    return;
  }
  state.proxyStatus = r;
  renderProxyStatus();
}

function renderProxyStatus() {
  const r = state.proxyStatus;
  if (!r) return;
  const table = document.getElementById("pxs-table");
  const summary = document.getElementById("pxs-summary");
  const c = r.counts || {};
  summary.textContent =
    `서버 ${r.scanned}대 조회 · 정상 ${c.ok || 0} · 차단 ${c.blocked || 0} · ` +
    `오프라인 ${c.offline || 0} · 확인불가 ${c.unknown || 0}` +
    (Object.keys(r.errors || {}).length ? ` · 조회 실패 서버: ${Object.keys(r.errors).join(", ")}` : "");
  table.innerHTML = "";
  const problemOnly = document.getElementById("pxs-problem-only").checked;
  let items = r.items || [];
  if (problemOnly) items = items.filter((i) => i.state !== "ok");
  if (!items.length) {
    table.append(el("div", { class: "empty" },
      problemOnly ? "문제 있는 프록시가 없습니다 ✓" : "프록시 저장소가 없습니다."));
    return;
  }
  const badge = (s) => {
    const map = { ok: ["up", "정상"], blocked: ["down", "차단됨"], offline: ["warn", "오프라인"], unknown: ["warn", "확인불가"] };
    const [cls, label] = map[s] || ["warn", s];
    return el("span", { class: `badge ${cls}` }, label);
  };
  const rows = [];
  items.forEach((i) => {
    const tr = el("tr", {}, [
      el("td", {}, i.instance_name),
      el("td", {}, el("span", { class: "link", onclick: () => openRepoDiff(i.repository) }, i.repository)),
      el("td", {}, i.format || ""),
      el("td", { class: "url" }, i.remote_url || ""),
      el("td", {}, badge(i.state)),
      el("td", {}, [
        i.detail || "",
        i.state !== "ok"
          ? el("button", { style: "margin-left:8px", onclick: (ev) => diagnoseProxy(ev, i) }, "진단")
          : null,
      ]),
    ]);
    rows.push(tr);
  });
  table.append(buildTable(["서버", "저장소", "포맷", "원격(remote)", "상태", "사유"], rows));
}

// Expand a diagnosis row (manager-side remote probe + one-click fixes).
async function diagnoseProxy(ev, item) {
  const tr = ev.target.closest("tr");
  if (tr.nextSibling && tr.nextSibling.classList && tr.nextSibling.classList.contains("pxs-diag")) {
    tr.nextSibling.remove();  // toggle off
    return;
  }
  const cell = el("td", { colspan: "6" }, "진단 중… (원격 프로브)");
  const diagRow = el("tr", { class: "pxs-diag" }, [cell]);
  tr.after(diagRow);
  let d;
  try {
    d = await api(
      `/api/proxy-status/diagnose?instance_id=${encodeURIComponent(item.instance_id)}` +
        `&repository=${encodeURIComponent(item.repository)}`
    );
  } catch (e) {
    cell.textContent = `진단 실패: ${e.message}`;
    return;
  }
  if (d.error) { cell.textContent = d.error; return; }
  cell.innerHTML = "";
  const probe = d.reachable
    ? `원격 응답 HTTP ${d.status_code} · ${d.elapsed_ms}ms`
    : `원격 연결 실패 (${d.probe_error || "오류"})`;
  const fixBtn = (action, label) => el("button", {
    style: "margin-right:6px",
    onclick: async () => {
      if (!confirm(`'${item.repository}' (${item.instance_name})에 적용: ${label}\n진행할까요?`)) return;
      try {
        const r = await api(
          `/api/proxy-status/fix?instance_id=${encodeURIComponent(item.instance_id)}` +
            `&repository=${encodeURIComponent(item.repository)}&action=${action}`,
          { method: "POST" }
        );
        toast(r.detail || "적용됨");
        loadProxyStatus();
      } catch (e) { toast(`적용 실패: ${e.message}`, "err"); }
    },
  }, label);
  cell.append(el("div", {}, [
    el("p", { class: "hint", style: "margin:4px 0" },
      `매니저→원격 프로브: ${probe} · 현재 설정: timeout ${d.timeout ?? "기본(20s)"} / ` +
      `재시도 ${d.retries ?? "기본(3)"} / auto-block ${d.auto_block ? "켜짐" : "꺼짐"}`),
    el("p", { style: "margin:4px 0" }, `→ ${d.suggestion}`),
    el("p", { class: "hint", style: "margin:4px 0" }, d.note || ""),
    el("div", { style: "margin-top:6px" }, [
      fixBtn("reset", "차단 초기화(재시도)"),
      fixBtn("timeout", "타임아웃 60초로 상향"),
      fixBtn("autoblock_off", "auto-block 해제"),
    ]),
  ]));
}

// ---- fleet-wide search ---------------------------------------------------

function setupSearch() {
  const form = document.getElementById("search-form");
  if (!form) return;
  form.addEventListener("submit", (ev) => { ev.preventDefault(); runSearch(); });
}

async function runSearch() {
  const q = document.getElementById("search-q").value.trim();
  const format = document.getElementById("search-format").value.trim();
  const repo = document.getElementById("search-repo").value.trim();
  const scope = document.getElementById("search-all").checked ? "all" : "monitoring";
  const status = document.getElementById("search-status");
  const box = document.getElementById("search-results");
  if (!q && !format && !repo) { toast("검색어를 입력하세요.", "err"); return; }
  box.innerHTML = "";
  status.textContent = "검색 중… (모든 서버 조회)";
  try {
    const params = new URLSearchParams({ q, format, repository: repo, scope });
    const r = await api(`/api/search?${params.toString()}`);
    status.textContent = `완료 · ${r.scanned}개 서버 · ${r.count}건`;
    renderSearchResults(r);
  } catch (e) {
    status.textContent = `검색 실패: ${e.message}`;
  }
}

function renderSearchResults(r) {
  const box = document.getElementById("search-results");
  box.innerHTML = "";
  const errIds = Object.keys(r.errors || {});
  if (errIds.length) {
    box.append(el("p", { class: "hint", style: "color:var(--amber)" },
      `조회 실패 서버 ${errIds.length}개 (권한/연결): ${errIds.join(", ")}`));
  }
  if (!r.hits.length) {
    box.append(el("div", { class: "empty" }, "일치하는 아티팩트가 없습니다."));
    return;
  }
  const rows = r.hits.map((h) => el("tr", {}, [
    el("td", {}, h.instance_name),
    el("td", {}, h.repository || ""),
    el("td", {}, [h.group, h.name].filter(Boolean).join(" : ") || h.name || ""),
    el("td", {}, h.version || ""),
    el("td", {}, h.format || ""),
  ]));
  box.append(buildTable(["서버", "저장소", "그룹 : 이름", "버전", "포맷"], rows));
}

// ---- overview ------------------------------------------------------------

function openStatusDetail(s) {
  const body = document.getElementById("status-modal-body");
  document.getElementById("status-modal-title").textContent = `${s.name} — 상태 상세`;
  body.innerHTML = "";

  body.append(el("div", { class: "url", style: "margin-bottom:10px" }, s.base_url));

  if (!s.reachable) {
    body.append(el("div", { class: "status-line down" }, "● 연결 불가"));
    body.append(el("div", { class: "site-error", style: "margin-top:8px" }, s.error || "원인 불명"));
    document.getElementById("status-modal").classList.remove("hidden");
    return;
  }

  const checks = s.checks || {};
  const keys = Object.keys(checks);
  const failed = keys.filter((k) => !checks[k]);

  if (!s.healthy) {
    body.append(el("div", { class: "status-line warn" },
      failed.length ? `● 주의 — 다음 점검이 실패했습니다 (${failed.length}건)` : "● 주의"));
  } else {
    body.append(el("div", { class: "status-line up" }, "● 정상"));
  }

  if (!keys.length) {
    body.append(el("div", { class: "empty" },
      "세부 점검 정보가 없습니다. (계정에 시스템 상태 조회 권한이 필요할 수 있어요)"));
  } else {
    const rows = keys.sort().map((k) =>
      el("tr", { class: checks[k] ? "" : "differs" }, [
        el("td", {}, checks[k]
          ? el("span", { class: "badge up" }, "정상")
          : el("span", { class: "badge down" }, "실패")),
        el("td", {}, k),
      ])
    );
    body.append(buildTable(["점검", "항목"], rows));
  }

  document.getElementById("status-modal").classList.remove("hidden");
}

document.getElementById("status-modal-close").addEventListener("click", () =>
  document.getElementById("status-modal").classList.add("hidden")
);
document.getElementById("status-modal").addEventListener("click", (ev) => {
  if (ev.target.id === "status-modal") ev.currentTarget.classList.add("hidden");
});

// Immediate skeleton: show every node right away (grouped chips) so the board
// is never blank while the (single) /api/topology probe runs.
function renderTopoSkeleton(insts) {
  const wrap = document.getElementById("topo-tree");
  if (!wrap) return;
  wrap.innerHTML = "";
  wrap.append(el("p", { class: "hint", style: "margin:0 0 8px" },
    "계위 상황판 불러오는 중 — 응답 오는 노드부터 표시됩니다…"));
  const groups = new Map();
  insts.forEach((i) => {
    const g = (i.group || "").trim() || "(그룹 미지정)";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(i);
  });
  const grid = el("div", { class: "topo-skel" });
  [...groups.keys()].forEach((g) => {
    const row = el("div", { class: "topo-skel-row" }, [el("span", { class: "topo-skel-group" }, g)]);
    groups.get(g).forEach((i) => {
      row.append(el("span", { class: "topo-skel-node", "data-node-id": i.id, title: i.base_url }, [
        el("span", { class: "topo-skel-dot", style: "background:var(--muted)" }),
        el("b", {}, i.name),
        el("span", { class: "topo-skel-ip" }, hostOf(i.base_url) || i.base_url),
      ]));
    });
    grid.append(row);
  });
  wrap.append(grid);
}

function colorTopoChip(id, s) {
  const dot = document.querySelector(
    `#topo-tree .topo-skel-node[data-node-id="${(window.CSS && CSS.escape) ? CSS.escape(id) : id}"] .topo-skel-dot`);
  if (!dot) return;
  dot.style.background = (!s || !s.reachable)
    ? "var(--red)" : (s.healthy === false ? "var(--amber)" : "var(--green)");
}

// The tier wallboard lives on the overview tab; it draws from /api/topology.
async function loadOverviewTree() {
  const wrap = document.getElementById("topo-tree");
  if (!wrap) return;
  const insts = state.instances || [];
  const token = (state.treeToken = (state.treeToken || 0) + 1);
  // 1) On the *first* load (no tree yet) render every node immediately, then
  //    color each as its probe answers — a slow node only delays its own chip.
  //    If a tier tree is already drawn, keep it (no skeleton flicker on refresh).
  if (insts.length >= 2 && !wrap.querySelector("svg")) {
    renderTopoSkeleton(insts);
    insts.forEach(async (i) => {
      let s = null;
      try { s = await api(`/api/instances/${encodeURIComponent(i.id)}/status`); }
      catch (e) { s = { reachable: false }; }
      if (state.treeToken === token) colorTopoChip(i.id, s);
    });
  }
  // 2) Full tier tree (edges + layout) replaces the skeleton when ready.
  try {
    const data = await api("/api/topology");
    if (state.treeToken === token) renderTopoTree(data);
  } catch (e) {
    if (state.treeToken !== token) return;
    wrap.innerHTML = "";
    wrap.append(el("p", { class: "hint" }, `상황판 로드 실패: ${e.message}`));
  }
}

// Loads the status cards on the 인스턴스 상태 tab (the wallboard is on 개요).
async function loadOverview() {
  const cards = document.getElementById("status-cards");

  // 1) Instantly render skeleton cards from the known instance list, so the
  //    page is responsive while the (potentially slow) status probe runs.
  if (state.instances && state.instances.length) {
    renderStatusCards(
      state.instances.map((i) => ({ ...i, loading: true })),
      state.groupOrder || []
    );
  } else {
    cards.innerHTML = "";
    cards.append(el("div", { class: "empty" }, "불러오는 중…"));
  }

  // 2) Group order (fast), then probe each node *independently* so one slow or
  //    unreachable node can't freeze the whole board at "측정 중…".
  let order = state.groupOrder || [];
  try {
    const ord = await api("/api/instances/group-order");
    order = (ord && ord.groups) || [];
    state.groupOrder = order;
  } catch (e) { /* keep previous order */ }

  const insts = state.instances || [];
  if (!insts.length) {
    // No known instance list — fall back to the aggregate endpoint.
    try {
      const st = await api("/api/status");
      if (!st.length) {
        cards.innerHTML = "";
        cards.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다. instances.yaml을 확인하세요."));
        return;
      }
      renderStatusCards(st, order);
    } catch (e) {
      cards.innerHTML = "";
      cards.append(el("div", { class: "empty" }, `상태를 불러올 수 없습니다: ${e.message}`));
    }
    return;
  }

  const statusMap = new Map(insts.map((i) => [i.id, { ...i, loading: true }]));
  const token = (state.overviewToken = (state.overviewToken || 0) + 1);
  const draw = () => {
    if (state.overviewToken === token) renderStatusCards([...statusMap.values()], order);
  };
  draw();
  await Promise.allSettled(insts.map(async (i) => {
    try {
      statusMap.set(i.id, await api(`/api/instances/${encodeURIComponent(i.id)}/status`));
    } catch (e) {
      statusMap.set(i.id, { ...i, reachable: false, healthy: false, error: e.message });
    }
    draw();
  }));
}

function fleetSummary(items) {
  const real = items.filter((i) => !i.loading);
  if (!real.length) return null;
  let up = 0, warn = 0, down = 0, repoSum = 0, respSum = 0, respN = 0;
  real.forEach((s) => {
    if (!s.reachable) down++;
    else if (s.healthy === false) warn++;
    else up++;
    if (s.repository_count != null) repoSum += s.repository_count;
    if (s.response_ms != null) { respSum += s.response_ms; respN++; }
  });
  const avg = respN ? Math.round(respSum / respN) : null;
  const chip = (cls, label, n) => el("span", { class: `fleet-chip ${cls}${n ? "" : " zero"}` }, `${label} ${n}`);
  return el("div", { class: "fleet-summary" }, [
    el("span", { class: "fleet-total" }, `서버 ${real.length}`),
    chip("up", "정상", up),
    chip("warn", "주의", warn),
    chip("down", "다운", down),
    el("span", { class: "fleet-sep" }, "·"),
    el("span", { class: "fleet-meta" }, `저장소 합계 ${repoSum.toLocaleString()}`),
    avg != null ? el("span", { class: "fleet-meta" }, `평균 응답 ${avg}ms`) : null,
  ]);
}

function renderStatusCards(items, order) {
  const cards = document.getElementById("status-cards");
  cards.innerHTML = "";
  const summary = fleetSummary(items);
  if (summary) cards.append(summary);

  const groups = new Map();
  items.forEach((s) => {
    const g = (s.group || "").trim() || "(그룹 미지정)";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(s);
  });
  const rank = (g) => {
    if (g === "(그룹 미지정)") return 1e9;
    const i = order.indexOf(g);
    return i === -1 ? 1e8 : i;
  };
  const names = [...groups.keys()].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, "ko"));
  const showHeaders = names.length > 1 || (names.length === 1 && names[0] !== "(그룹 미지정)");

  names.forEach((g) => {
    const list = groups.get(g);
    if (showHeaders) {
      const loading = list.some((s) => s.loading);
      const up = list.filter((s) => s.reachable && s.healthy).length;
      cards.append(el("div", { class: "group-head" }, [
        el("span", { class: "group-name" }, g),
        el("span", { class: "group-count" }, loading ? `${list.length}대` : `${up}/${list.length} 정상`),
      ]));
    }
    const grid = el("div", { class: "cards" });
    list.forEach((s) => grid.append(makeStatusCard(s)));
    cards.append(grid);
  });
}

function makeStatusCard(s) {
  let badge;
  if (s.loading) badge = el("span", { class: "badge loading-badge" }, "측정 중…");
  else if (!s.reachable) badge = el("span", { class: "badge down status-badge", title: "클릭하여 원인 보기", onclick: () => openStatusDetail(s) }, "연결 불가");
  else if (!s.healthy) badge = el("span", { class: "badge warn status-badge", title: "클릭하여 원인 보기", onclick: () => openStatusDetail(s) }, "주의");
  else badge = el("span", { class: "badge up status-badge", title: "클릭하여 점검 상세 보기", onclick: () => openStatusDetail(s) }, "정상");

  const metrics = el("div", { class: "metrics" }, [
    el("div", { class: "metric" }, [
      el("div", { class: "label" }, "응답시간"),
      el("div", { class: "value" }, s.loading ? "…" : (s.response_ms != null ? `${s.response_ms} ms` : "—")),
    ]),
    el("div", { class: "metric" }, [
      el("div", { class: "label" }, "Repository"),
      el("div", { class: "value", style: "text-align:center" }, s.loading ? "…" : (s.repository_count != null ? s.repository_count : "—")),
    ]),
  ]);

  const card = el("div", { class: "card" }, [
    el("div", { class: "name" }, [s.name, " ", badge]),
    el("a", {
      class: "url url-link",
      href: s.base_url,
      target: "_blank",
      rel: "noopener noreferrer",
      title: "새 탭에서 이 서버의 Nexus 열기",
    }, s.base_url),
    metrics,
  ]);
  if (!s.loading && s.error) card.append(el("div", { class: "url", style: "color:var(--red);margin-top:8px" }, s.error));
  return card;
}

function fmtUptime(ms) {
  if (ms == null) return "—";
  const d = Math.floor(ms / 86400000);
  const h = Math.floor((ms % 86400000) / 3600000);
  return d > 0 ? `${d}일 ${h}시간` : `${h}시간`;
}

async function loadMetrics() {
  const container = document.getElementById("metrics-table");
  container.innerHTML = "";
  let list;
  try {
    list = await api("/api/metrics");
  } catch (e) {
    container.append(el("div", { class: "empty" }, `메트릭 조회 실패: ${e.message}`));
    return;
  }
  if (!list.length) {
    container.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다."));
    return;
  }
  const rows = list.map((m) => {
    if (!m.reachable) {
      return el("tr", {}, [
        el("td", {}, m.name),
        el("td", { colspan: "4", class: "site-error" }, `조회 불가: ${m.error || ""} (nx-metrics-all 권한 필요)`),
      ]);
    }
    const pct = m.heap_usage_pct;
    const pctCls = pct == null ? "" : pct >= 90 ? "usage-crit" : pct >= 80 ? "usage-warn" : "";
    return el("tr", {}, [
      el("td", {}, m.name),
      el("td", { class: "num" }, fmtBytes(m.heap_used_bytes)),
      el("td", { class: "num" }, fmtBytes(m.heap_max_bytes)),
      el("td", { class: `num ${pctCls}` }, pct != null ? `${pct}%` : "—"),
      el("td", { class: "num" }, m.thread_count != null ? m.thread_count.toLocaleString() : "—"),
      el("td", {}, fmtUptime(m.uptime_ms)),
    ]);
  });
  container.append(buildTable(["노드", "Heap 사용", "Heap 최대", "Heap %", "스레드", "가동시간"], rows));
}

function usagePct(b) {
  const used = b.total_size_bytes;
  const avail = b.available_space_bytes;
  if (used == null || avail == null) return null;
  const total = used + avail;
  if (total <= 0) return null;
  return (used / total) * 100;
}

function usageCell(b) {
  const pct = usagePct(b);
  if (pct == null) return el("td", { class: "num" }, "—");
  const cls = pct >= 90 ? "usage-crit" : pct >= 80 ? "usage-warn" : "";
  return el("td", { class: `num ${cls}`, title: `사용 ${fmtBytes(b.total_size_bytes)} / 전체 ${fmtBytes(b.total_size_bytes + b.available_space_bytes)}` }, `${pct.toFixed(0)}%`);
}

async function loadDiskForecast(sample = false) {
  const table = document.getElementById("df-table");
  const status = document.getElementById("df-status");
  if (!table) return;
  if (sample) status.textContent = "수집 중…";
  let r;
  try {
    r = await api(`/api/disk-forecast${sample ? "?sample=true" : ""}`);
  } catch (e) {
    status.textContent = `조회 실패: ${e.message}`;
    return;
  }
  const c = r.counts || {};
  status.textContent = `위험 ${c.crit || 0} · 주의 ${c.warn || 0} · 정상 ${c.ok || 0}`;
  table.innerHTML = "";
  const rows = (r.stores || []).map((s) => {
    const badge = { crit: ["down", "위험"], warn: ["warn", "주의"], ok: ["up", "정상"] }[s.state] || ["warn", s.state];
    const eta = s.days_to_90 == null
      ? (s.growth_per_day != null && s.growth_per_day <= 0 ? "증가 없음" : "표본 부족")
      : s.days_to_90 <= 0 ? "도달" : `약 ${Math.round(s.days_to_90)}일 후`;
    return el("tr", {}, [
      el("td", {}, s.instance_name),
      el("td", {}, s.store),
      el("td", { class: "num" }, `${fmtBytes(s.used_bytes)} / ${fmtBytes(s.total_bytes)}`),
      el("td", { class: "num" }, `${s.pct}%`),
      el("td", { class: "num" }, s.growth_per_day == null ? "—" : `${fmtBytes(s.growth_per_day)}/일`),
      el("td", {}, eta),
      el("td", {}, el("span", { class: `badge ${badge[0]}` }, badge[1])),
    ]);
  });
  if (!rows.length) {
    table.append(el("div", { class: "empty" }, "아직 수집된 표본이 없습니다. '지금 수집 + 갱신'을 눌러 첫 표본을 만드세요."));
    return;
  }
  table.append(buildTable(["서버", "Blob store", "사용/전체", "사용률", "일일 증가", "90% 도달", "상태"], rows));
}

// ---- blob usage trend charts (feature) -----------------------------------

function renderDiskChart(series) {
  // usage% (0~100) over time, with 80/90% guide lines. Pure SVG (no library).
  const W = 520, H = 150, padL = 34, padR = 10, padT = 10, padB = 22;
  const pts = series.points || [];
  const wrap = el("div", { class: "infra-chart" });
  wrap.append(el("div", { class: "infra-chart-head" }, [
    el("span", { class: "infra-name" }, `${series.instance_name} · ${series.store}`),
    el("span", { class: "url" }, pts.length ? `${pts[pts.length - 1].pct}% (표본 ${pts.length})` : "표본 없음"),
  ]));
  if (pts.length < 2) {
    wrap.append(el("div", { class: "empty" }, "표본이 부족합니다(2개 이상 필요)."));
    return wrap;
  }
  const ts = pts.map((p) => p.t);
  const tmin = Math.min(...ts), tmax = Math.max(...ts), tspan = Math.max(tmax - tmin, 1);
  const xOf = (t) => padL + ((t - tmin) / tspan) * (W - padL - padR);
  const yOf = (pct) => H - padB - (Math.max(0, Math.min(100, pct)) / 100) * (H - padT - padB);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "infra-svg" });
  svg.append(svgEl("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, class: "axis" }));
  svg.append(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: H - padB, class: "axis" }));
  [[90, "var(--red)"], [80, "var(--amber)"]].forEach(([lvl, col]) => {
    const y = yOf(lvl);
    svg.append(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, stroke: col, "stroke-dasharray": "5 4", "stroke-width": 1 }));
    svg.append(svgEl("text", { x: padL + 2, y: y - 2, class: "axis-label" }, `${lvl}%`));
  });
  const d = pts.map((p, i) => `${i ? "L" : "M"}${xOf(p.t).toFixed(1)} ${yOf(p.pct).toFixed(1)}`).join(" ");
  svg.append(svgEl("path", { d, class: "infra-line", fill: "none", stroke: "var(--accent)", "stroke-width": 1.6 }));
  svg.append(svgEl("text", { x: padL, y: H - 6, class: "axis-label" }, new Date(tmin * 1000).toLocaleDateString()));
  svg.append(svgEl("text", { x: W - padR, y: H - 6, class: "axis-label", "text-anchor": "end" }, new Date(tmax * 1000).toLocaleDateString()));
  wrap.append(svg);
  return wrap;
}

async function loadDiskCharts() {
  const box = document.getElementById("disk-charts");
  const status = document.getElementById("dc-status");
  if (!box) return;
  const days = Number(document.getElementById("dc-days").value) || 60;
  status.textContent = "불러오는 중…";
  let r;
  try {
    r = await api(`/api/disk-history?days=${days}`);
  } catch (e) {
    status.textContent = `조회 실패: ${e.message}`;
    return;
  }
  const stores = r.stores || [];
  status.textContent = `blob store ${stores.length}개`;
  box.innerHTML = "";
  if (!stores.length) {
    box.append(el("div", { class: "empty" }, "아직 수집된 표본이 없습니다(6시간마다 자동 수집)."));
    return;
  }
  const grid = el("div", { class: "infra-grid" });
  stores.forEach((s) => grid.append(renderDiskChart(s)));
  box.append(grid);
}

// ---- 정리 후보(휴면 아티팩트) (feature) -----------------------------------

function fillCleanupInstances() {
  const sel = document.getElementById("cc-inst");
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = "";
  (state.instances || []).forEach((i) => sel.append(el("option", { value: i.id }, i.name)));
  if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
}

async function loadCleanupCandidates() {
  const sel = document.getElementById("cc-inst");
  const status = document.getElementById("cc-status");
  const table = document.getElementById("cc-table");
  const summary = document.getElementById("cc-summary");
  if (!sel || !sel.value) { toast("서버를 선택하세요.", "err"); return; }
  const days = Number(document.getElementById("cc-days").value) || 90;
  status.textContent = "스캔 중… (저장소가 많으면 시간이 걸립니다)";
  table.innerHTML = ""; summary.innerHTML = "";
  let r;
  try {
    r = await api(`/api/instances/${encodeURIComponent(sel.value)}/cleanup-candidates?days=${days}`);
  } catch (e) {
    status.textContent = `스캔 실패: ${e.message}`;
    return;
  }
  status.textContent = "";
  summary.append(
    summaryCard("휴면 자산", (r.dormant_assets || 0).toLocaleString()),
    summaryCard("휴면 용량", fmtBytes(r.dormant_size_bytes || 0)),
    summaryCard(`기준`, `${r.days}일+ 미사용`)
  );
  const repos = (r.repositories || []).filter((x) => (x.dormant_assets || 0) > 0 || x.error);
  if (!repos.length) {
    table.append(el("div", { class: "empty" }, "휴면 자산이 없습니다 ✓"));
    return;
  }
  const rows = repos.map((x) => {
    if (x.error) {
      return el("tr", {}, [
        el("td", {}, x.repository),
        el("td", { class: "site-error", colspan: "4" }, x.error),
      ]);
    }
    const biggest = (x.largest || [])[0];
    return el("tr", {}, [
      el("td", {}, x.repository),
      el("td", {}, x.type || "—"),
      el("td", { class: "num" }, `${(x.dormant_assets || 0).toLocaleString()} / ${(x.total_assets || 0).toLocaleString()}`),
      el("td", { class: "num" }, fmtBytes(x.dormant_size_bytes || 0) + (x.truncated ? " *" : "")),
      el("td", { title: biggest ? biggest.path : "" }, biggest ? `${biggest.path.split("/").pop()} (${fmtBytes(biggest.size_bytes || 0)})` : "—"),
    ]);
  });
  table.append(buildTable(["저장소", "타입", "휴면/전체 자산", "휴면 용량", "가장 큰 휴면 자산"], rows));
  if (repos.some((x) => x.truncated)) {
    table.append(el("p", { class: "hint" }, "* 일부 대형 저장소는 최대 50페이지까지만 스캔했습니다(하한값)."));
  }
}

async function loadBlobstores() {
  loadDiskForecast();
  const container = document.getElementById("blobstore-table");
  container.innerHTML = "";
  let sites = [];
  try {
    sites = await api("/api/blobstores");
  } catch (e) {
    container.append(el("div", { class: "empty" }, `Blob store 조회 실패: ${e.message}`));
    return;
  }
  if (!sites.length) {
    container.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다."));
    return;
  }

  const rows = [];
  let grandUsed = 0;
  let grandBlobs = 0;
  let reachableSites = 0;

  sites.forEach((site) => {
    if (!site.reachable) {
      rows.push(
        el("tr", { class: "site-start" }, [
          el("td", { class: "site-cell" }, site.name),
          el("td", { colspan: "6", class: "site-error" }, `조회 불가: ${site.error || ""}`),
        ])
      );
      return;
    }
    reachableSites += 1;
    if (site.total_size_bytes != null) grandUsed += site.total_size_bytes;
    if (site.blob_count != null) grandBlobs += site.blob_count;

    if (!site.blobstores.length) {
      rows.push(
        el("tr", { class: "site-start" }, [
          el("td", { class: "site-cell" }, site.name),
          el("td", { colspan: "6", class: "empty" }, "Blob store 없음"),
        ])
      );
      return;
    }
    // First row of a site carries the site name.
    site.blobstores.forEach((b, idx) =>
      rows.push(
        el("tr", { class: idx === 0 ? "site-start" : "" }, [
          el("td", { class: "site-cell" }, idx === 0 ? site.name : ""),
          el("td", {}, b.name),
          el("td", {}, b.type || "—"),
          el("td", { class: "num" }, fmtBytes(b.total_size_bytes)),
          el("td", { class: "num" }, fmtBytes(b.available_space_bytes)),
          usageCell(b),
          el("td", { class: "num" }, b.blob_count != null ? b.blob_count.toLocaleString() : "—"),
        ])
      )
    );
    // Per-site subtotal when a site has more than one blob store.
    if (site.blobstores.length > 1) {
      rows.push(
        el("tr", { class: "subtotal" }, [
          el("td", { class: "site-cell" }, ""),
          el("td", { class: "subtotal-label" }, "사이트 합계"),
          el("td", {}, ""),
          el("td", { class: "num" }, fmtBytes(site.total_size_bytes)),
          el("td", {}, ""),
          el("td", {}, ""),
          el("td", { class: "num" }, site.blob_count != null ? site.blob_count.toLocaleString() : "—"),
        ])
      );
    }
  });

  // Grand total across all reachable sites.
  rows.push(
    el("tr", { class: "grand-total" }, [
      el("td", { class: "site-cell" }, "전체 합계"),
      el("td", {}, `${reachableSites}개 사이트`),
      el("td", {}, ""),
      el("td", { class: "num" }, fmtBytes(grandUsed)),
      el("td", {}, ""),
      el("td", {}, ""),
      el("td", { class: "num" }, grandBlobs.toLocaleString()),
    ])
  );

  container.append(
    buildTable(["사이트", "Blob Store", "유형", "사용량", "가용 공간", "사용률", "Blob 수"], rows)
  );
}

// ---- infra check (ping charts) -------------------------------------------

function svgEl(tag, attrs = {}, children = []) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    n.append(c.nodeType ? c : document.createTextNode(String(c)));
  });
  return n;
}

function pingColor(c) {
  return c === "crit" ? "var(--red)" : c === "warn" ? "var(--amber)" : "var(--accent)";
}

function setupInfra() {
  document.querySelectorAll("#infra-range button").forEach((b) => {
    b.addEventListener("click", () => {
      state.infraDays = Number(b.dataset.days);
      document.querySelectorAll("#infra-range button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      loadInfra();
    });
  });
  document.getElementById("infra-refresh").addEventListener("click", loadInfra);
  // default 1일 active
  const first = document.querySelector('#infra-range button[data-days="1"]');
  if (first) first.classList.add("active");
}

async function loadInfra() {
  const container = document.getElementById("infra-charts");
  container.innerHTML = "";
  container.append(el("div", { class: "empty" }, "불러오는 중…"));
  const days = state.infraDays || 1;
  let data;
  try {
    data = await api(`/api/ping-history?days=${days}`);
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `조회 실패: ${e.message}`));
    return;
  }
  const wl = document.getElementById("infra-warn-label");
  const cl = document.getElementById("infra-crit-label");
  if (wl) wl.textContent = `+${data.warn_pct}% 이상`;
  if (cl) cl.textContent = `+${data.crit_pct}% 이상`;
  container.innerHTML = "";
  if (!data.series.length) {
    container.append(el("div", { class: "empty" }, "측정 데이터가 아직 없습니다. 잠시 후 다시 확인하세요. (백그라운드에서 누적 중)"));
    return;
  }
  // Group the charts and lay them out 3-per-row (each 1/3 width).
  const order = state.groupOrder || [];
  const groups = new Map();
  data.series.forEach((s) => {
    const g = (s.group || "").trim() || "(그룹 미지정)";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(s);
  });
  const rank = (g) => (g === "(그룹 미지정)" ? 1e9 : (order.indexOf(g) === -1 ? 1e8 : order.indexOf(g)));
  const names = [...groups.keys()].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, "ko"));
  const showHeads = names.length > 1 || (names.length === 1 && names[0] !== "(그룹 미지정)");

  const grid = el("div", { class: "infra-grid" });
  names.forEach((g) => {
    if (showHeads) grid.append(el("div", { class: "infra-grouphead" }, g));
    groups.get(g).forEach((s) => grid.append(renderInfraChart(s)));
  });
  container.append(grid);
}

function renderInfraChart(s, opts = {}) {
  const unit = opts.unit || "ms";
  const wrap = el("div", { class: "infra-chart" });
  const headNote =
    s.baseline != null ? `평소(중앙값) ${s.baseline} ${unit}` : (s.detail ? "측정 실패" : "데이터 없음");
  wrap.append(el("div", { class: "infra-chart-head" }, [
    el("span", { class: "infra-name" }, s.name),
    el("span", { class: "url" }, headNote),
  ]));
  if (!s.points.length) {
    const msg = s.detail || "측정 데이터가 아직 없습니다.";
    wrap.append(el("div", { class: s.detail ? "empty site-error" : "empty" }, msg));
    return wrap;
  }
  const W = 520, H = 200, padL = 44, padR = 10, padT = 12, padB = 26;
  const ts = s.points.map((p) => p.t);
  const tmin = Math.min(...ts), tmax = Math.max(...ts);
  const tspan = Math.max(tmax - tmin, 1);
  const vmax = (Math.max(s.baseline || 0, ...s.points.map((p) => p.v)) || 1) * 1.15;
  const xOf = (t) => padL + ((t - tmin) / tspan) * (W - padL - padR);
  const yOf = (v) => H - padB - (v / vmax) * (H - padT - padB);

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "infra-svg" });
  svg.append(svgEl("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, class: "axis" }));
  svg.append(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: H - padB, class: "axis" }));
  if (s.baseline != null) {
    const by = yOf(s.baseline);
    svg.append(svgEl("line", { x1: padL, y1: by, x2: W - padR, y2: by, class: "baseline" }));
  }
  const coords = s.points.map((p) => ({ x: xOf(p.t), y: yOf(p.v), p }));
  const d = coords.map((c, i) => `${i ? "L" : "M"}${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ");
  svg.append(svgEl("path", { d, class: "infra-line", fill: "none" }));
  coords.forEach((c) =>
    svg.append(svgEl("circle", { cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: c.p.color === "ok" ? 2.2 : 3.4, fill: pingColor(c.p.color) }))
  );

  // Hover crosshair + highlight ring (hidden until mousemove).
  const crosshair = svgEl("line", { x1: 0, y1: padT, x2: 0, y2: H - padB, class: "crosshair", style: "display:none" });
  const hi = svgEl("circle", { cx: 0, cy: 0, r: 5, class: "hi", style: "display:none" });
  svg.append(crosshair, hi);

  svg.append(svgEl("text", { x: 4, y: padT + 8, class: "axis-label" }, `${Math.round(vmax)}${unit}`));
  svg.append(svgEl("text", { x: padL, y: H - 8, class: "axis-label" }, new Date(tmin * 1000).toLocaleString()));
  svg.append(svgEl("text", { x: W - padR, y: H - 8, class: "axis-label", "text-anchor": "end" }, new Date(tmax * 1000).toLocaleString()));
  wrap.append(svg);

  const tip = el("div", { class: "infra-tip" });
  wrap.append(tip);

  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const vbX = ((ev.clientX - rect.left) / rect.width) * W;
    let best = coords[0], bd = Infinity;
    coords.forEach((c) => { const dx = Math.abs(c.x - vbX); if (dx < bd) { bd = dx; best = c; } });
    crosshair.setAttribute("x1", best.x);
    crosshair.setAttribute("x2", best.x);
    crosshair.style.display = "";
    hi.setAttribute("cx", best.x);
    hi.setAttribute("cy", best.y);
    hi.setAttribute("stroke", pingColor(best.p.color));
    hi.style.display = "";
    // Labelled lines: 응답속도 / 한국시간 / 로컬시간 (the last only when the
    // server has a timezone configured).
    const dt = new Date(best.p.t * 1000);
    const tz = ((state.instances || []).find((i) => i.id === s.id) || {}).timezone;
    let when = `한국시간: ${dt.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}`;
    if (tz) {
      try {
        when += `\n로컬시간: ${dt.toLocaleString("ko-KR", { timeZone: tz })} (${tz})`;
      } catch (e) { /* invalid timezone string — keep Korea time only */ }
    }
    tip.textContent = `응답속도: ${best.p.v} ${unit}\n${when}`;
    tip.style.display = "block";
    const wr = wrap.getBoundingClientRect();
    let left = ev.clientX - wr.left + 12;
    if (left + tip.offsetWidth > wr.width - 4) left = ev.clientX - wr.left - tip.offsetWidth - 12;
    tip.style.left = `${Math.max(2, left)}px`;
    tip.style.top = `${Math.max(2, ev.clientY - wr.top - 28)}px`;
  });
  svg.addEventListener("mouseleave", () => {
    tip.style.display = "none";
    crosshair.style.display = "none";
    hi.style.display = "none";
  });
  return wrap;
}

// ---- topology ------------------------------------------------------------

function setupTopology() {
  document.getElementById("topo-refresh").addEventListener("click", loadTopology);
  document.getElementById("topo-probe").addEventListener("change", loadTopology);
  document.getElementById("pxs-refresh").addEventListener("click", loadProxyStatus);
  document.getElementById("pxs-fix-all").addEventListener("click", fixAllBlockedProxies);
  document.getElementById("pxs-problem-only").addEventListener("change", renderProxyStatus);
  document.getElementById("topo-reset").addEventListener("click", () => {
    localStorage.removeItem("topoPos");
    toast("배치를 초기화했습니다 (자동 배치)");
    loadOverviewTree();
  });
}

// Hierarchical status board: tiers derived from internal proxy links
// (e.g. DMZ → HQ → 15 global DCs), drawn as an SVG tree like a wallboard.
function renderTopoTree(data) {
  const wrap = document.getElementById("topo-tree");
  if (!wrap) return;
  wrap.innerHTML = "";
  const nodes = data.nodes || [];
  if (nodes.length < 2) return;
  const byId = {};
  nodes.forEach((n) => { byId[n.id] = n; });

  // child --proxy--> parent(upstream). Pick the most-proxied upstream as the
  // primary parent for layout; draw every internal edge.
  const parentOf = {};
  const edges = [];
  nodes.forEach((n) => {
    const counts = {};
    const broken = {};
    const linkRepos = {};
    (n.proxies || []).forEach((p) => {
      if (p.internal && p.target_id && byId[p.target_id] && p.target_id !== n.id) {
        counts[p.target_id] = (counts[p.target_id] || 0) + 1;
        if (p.broken) broken[p.target_id] = true;
        (linkRepos[p.target_id] = linkRepos[p.target_id] || []).push(p);
      }
    });
    const ids = Object.keys(counts);
    ids.forEach((pid) => edges.push({
      from: pid, to: n.id, count: counts[pid], broken: !!broken[pid],
      repos: linkRepos[pid] || [],
    }));
    if (ids.length) parentOf[n.id] = ids.sort((a, b) => counts[b] - counts[a])[0];
  });
  // Manual tiers (계위 set in 서버 설정) let the board be arranged even when
  // there are no internal proxy links to derive a hierarchy from.
  const useManualTier = nodes.some((n) => (n.tier || 0) > 0);
  if (!edges.length && !useManualTier) {
    wrap.append(el("p", { class: "hint" }, "내부(서버 간) 프록시 링크가 없어 계위 트리를 그릴 수 없습니다. (서버 설정에서 계위를 지정하면 수동 배치할 수 있습니다)"));
    return;
  }

  // Tier (depth) per node: roots are the top of the hierarchy (e.g. DMZ).
  // When every node has an internal upstream (mutual proxying / cycles),
  // promote the most-referenced upstream(s) to be the root tier.
  let rootIds = nodes.filter((n) => parentOf[n.id] == null).map((n) => n.id);
  if (!rootIds.length) {
    const indeg = {};
    edges.forEach((e) => { indeg[e.from] = (indeg[e.from] || 0) + e.count; });
    const top = Math.max(...Object.values(indeg));
    rootIds = Object.keys(indeg).filter((k) => indeg[k] === top);
    rootIds.forEach((id) => { delete parentOf[id]; });
  }
  const depth = {};
  rootIds.forEach((id) => { depth[id] = 0; });
  for (let i = 0; i < 20; i++) {
    let changed = false;
    nodes.forEach((n) => {
      const p = parentOf[n.id];
      if (p != null && depth[p] != null && depth[n.id] == null) {
        depth[n.id] = depth[p] + 1;
        changed = true;
      }
    });
    if (!changed) break;
  }
  // Anything still unplaced (cycle islands) goes right below the roots.
  nodes.forEach((n) => { if (depth[n.id] == null) depth[n.id] = 1; });

  let layers = [];
  nodes.forEach((n) => {
    const d = depth[n.id];
    (layers[d] = layers[d] || []).push(n);
  });
  layers = layers.filter((l) => l && l.length);  // compact (no sparse holes)

  // Manual tier override: when any node has a 계위(tier) set, arrange the rows
  // strictly by that number (1=top .. N). Nodes left at 0 drop to the bottom.
  if (useManualTier) {
    const maxT = Math.max(...nodes.map((n) => n.tier || 0));
    const byTier = [];
    nodes.forEach((n) => {
      const t = (n.tier || 0) > 0 ? n.tier : maxT + 1;
      (byTier[t] = byTier[t] || []).push(n);
    });
    layers = byTier.filter((l) => l && l.length);
  }

  const NW = 150, NH = 48, HGAP = 22, VGAP = 100, PAD = 70;
  const maxCount = Math.max(...layers.map((l) => l.length));
  let width = Math.max(maxCount * (NW + HGAP) - HGAP + PAD * 2, 640);
  let height = layers.length * VGAP + 30;
  const pos = {};
  layers.forEach((layer, li) => {
    if (!layer) return;
    if (li > 0) {
      layer.sort((a, b) => {
        const pa = pos[parentOf[a.id]] ? pos[parentOf[a.id]].x : 0;
        const pb = pos[parentOf[b.id]] ? pos[parentOf[b.id]].x : 0;
        return pa - pb || a.name.localeCompare(b.name);
      });
    }
    const total = layer.length * (NW + HGAP) - HGAP;
    const x0 = (width - total) / 2;
    layer.forEach((n, i) => {
      pos[n.id] = { x: x0 + i * (NW + HGAP), y: 26 + li * VGAP };
    });
  });

  // User-arranged positions (drag & drop) override the automatic layout.
  // Only accept FINITE coordinates — typeof NaN === "number", so a corrupt
  // saved value would otherwise poison width/height and collapse the board.
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("topoPos") || "{}"); } catch (e) { saved = {}; }
  nodes.forEach((n) => {
    const sp = saved[n.id];
    if (sp && Number.isFinite(sp.x) && Number.isFinite(sp.y)) pos[n.id] = { x: sp.x, y: sp.y };
  });
  // Final guard: every node must have a finite position (fallback to origin
  // so one bad value can never blank the whole board).
  nodes.forEach((n, i) => {
    const p = pos[n.id];
    if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) {
      pos[n.id] = { x: 24 + (i % 6) * (NW + HGAP), y: 26 + Math.floor(i / 6) * VGAP };
    }
  });

  // Fit the canvas to the actual content (no dead margins).
  const labelRoom = 24;
  const dx = labelRoom - Math.min(...nodes.map((n) => pos[n.id].x));
  const dy = 24 - Math.min(...nodes.map((n) => pos[n.id].y));
  nodes.forEach((n) => { pos[n.id].x += dx; pos[n.id].y += dy; });
  width = Math.max(...nodes.map((n) => pos[n.id].x)) + NW + 20;
  height = Math.max(...nodes.map((n) => pos[n.id].y)) + NH + 20;

  // Sticky layout: once the user has arranged the board (≥1 saved position),
  // freeze EVERY node's coordinates so a later change in proxy structure (or a
  // node briefly going unreachable) can't re-flow the un-dragged nodes — which
  // looked like the board "resetting". "배치 초기화" clears this and re-derives.
  if (Object.keys(saved).length) {
    const store = {};
    nodes.forEach((n) => { store[n.id] = { x: Math.round(pos[n.id].x), y: Math.round(pos[n.id].y) }; });
    try { localStorage.setItem("topoPos", JSON.stringify(store)); } catch (e) { /* quota */ }
  }

  let s = "";
  // Arrowheads: the proxy direction is child → upstream(parent), so paths are
  // drawn child-top → parent-bottom with a marker-end pointing at the parent.
  s += `<defs>` +
    `<marker id="tt-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path class="tt-arrow-head" d="M0,0L10,5L0,10z"/></marker>` +
    `<marker id="tt-arrow-broken" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path class="tt-arrow-head broken" d="M0,0L10,5L0,10z"/></marker>` +
    `</defs>`;
  // Edges, tagged so dragging can re-route them (visible line + a wide
  // invisible twin that makes hovering for the tooltip easy).
  const edgeD = (e) => {
    const a = pos[e.from], b = pos[e.to];        // a = parent(arrow target), b = child(start)
    const acx = a.x + NW / 2, bcx = b.x + NW / 2;
    const acy = a.y + NH / 2, bcy = b.y + NH / 2;
    // Attach each line end to the side of the node that FACES the other node:
    // if the connected node is above, start from the top edge; else the bottom.
    const aTop = bcy < acy;   // child sits above parent → parent attaches on top
    const bTop = acy < bcy;   // parent sits above child → child attaches on top
    const ay = aTop ? a.y : a.y + NH;
    const by = bTop ? b.y : b.y + NH;
    // Short straight run on each side keeps the arrow orientation well-defined.
    const K = Math.max(16, Math.abs(ay - by) * 0.3);
    const c1y = by + (bTop ? -K : K);
    const c2y = ay + (aTop ? -K : K);
    return {
      d: `M${bcx},${by} C${bcx},${c1y} ${acx},${c2y} ${acx},${ay}`,
      lx: (acx + bcx) / 2, ly: (ay + by) / 2 - 4,
    };
  };
  edges.forEach((e, i) => {
    if (!pos[e.from] || !pos[e.to]) return;
    const g = edgeD(e);
    const cls = e.broken ? "tt-edge broken" : "tt-edge";
    s += `<path class="${cls}" data-ei="${i}" marker-end="url(#${e.broken ? "tt-arrow-broken" : "tt-arrow"})" d="${g.d}"/>` +
      `<path class="tt-edge-hit" data-ei="${i}" d="${g.d}"/>` +
      (e.count > 1 ? `<text x="${g.lx}" y="${g.ly}" class="tt-count" data-ei="${i}">${e.count}</text>` : "");
  });
  // Nodes: card with a status dot in the corner.
  nodes.forEach((n) => {
    const p = pos[n.id];
    if (!p) return;
    // down (truly unreachable) / warn (answered but auth/permission issue) / up.
    const cls = !n.reachable ? "tt-node down" : (n.error ? "tt-node warn" : "tt-node up");
    const host = hostOf(n.base_url) || n.base_url;
    const note = !n.reachable ? " · 연결 불가" : (n.error ? " · " + n.error : "");
    s += `<g class="${cls}" data-id="${escapeHtml(n.id)}" transform="translate(${p.x},${p.y})">` +
      `<rect width="${NW}" height="${NH}" rx="11"/>` +
      `<circle class="tt-dot" cx="${NW - 13}" cy="13" r="4"/>` +
      `<text x="${NW / 2}" y="20" class="tt-name">${escapeHtml(n.name)}</text>` +
      `<text x="${NW / 2}" y="37" class="tt-host">${escapeHtml(host)}</text>` +
      `<title>${escapeHtml(n.name)} · ${escapeHtml(n.base_url)}${escapeHtml(note)}</title></g>`;
  });

  wrap.innerHTML =
    `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">${s}</svg>`;

  // Drag & drop arrangement: drag a node anywhere; edges follow live and the
  // position is remembered (localStorage). A plain click still opens Nexus.
  const svg = wrap.querySelector("svg");
  // Grow the canvas so a node dragged toward an edge is never clipped (the
  // wrap scrolls/expands to contain it). Width is a closure var read by the
  // drag scale math, so updating it keeps dragging consistent.
  const growCanvas = () => {
    const w = Math.max(width, Math.max(...nodes.map((n) => pos[n.id].x)) + NW + 24);
    const h = Math.max(height, Math.max(...nodes.map((n) => pos[n.id].y)) + NH + 24);
    if (w !== width || h !== height) {
      width = w; height = h;
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("width", width);
      svg.setAttribute("height", height);
    }
  };
  const refreshEdges = () => {
    edges.forEach((e, i) => {
      if (!pos[e.from] || !pos[e.to]) return;
      const g = edgeD(e);
      svg.querySelectorAll(`path[data-ei="${i}"]`).forEach((p) => p.setAttribute("d", g.d));
      const label = svg.querySelector(`text[data-ei="${i}"]`);
      if (label) { label.setAttribute("x", g.lx); label.setAttribute("y", g.ly); }
    });
  };

  // Click on an edge (or its count) → list the proxy repositories that make
  // up that link, in the shared repo modal. Repo names jump to the deep diff.
  const showEdgeRepos = (e) => {
    const from = byId[e.from], to = byId[e.to];
    document.getElementById("repo-modal-title").textContent =
      `프록시 링크 — ${to.name} → ${from.name} (저장소 ${e.count}개)`;
    const body = document.getElementById("repo-modal-body");
    body.innerHTML = "";
    const thead = el("thead", {}, el("tr", {}, [
      el("th", {}, "저장소"), el("th", {}, "원격 URL"), el("th", {}, "상태"),
    ]));
    const rows = (e.repos || []).map((p) => el("tr", {}, [
      el("td", {}, el("a", {
        href: "#",
        title: "이 저장소의 서버 간 설정 비교 열기",
        onclick: (ev) => { ev.preventDefault(); openRepoDiff(p.repository); },
      }, p.repository)),
      el("td", {}, p.remote_url || ""),
      el("td", {}, el("span", { class: `badge ${p.broken ? "down" : "up"}` }, p.broken ? "끊김" : "정상")),
    ]));
    body.append(el("table", {}, [thead, el("tbody", {}, rows)]));
    document.getElementById("repo-modal").classList.remove("hidden");
  };

  // Edge hover tooltip ("OC2a → DMZ1 · 프록시 74개") + highlight.
  const tip = el("div", { class: "topo-tip" });
  wrap.append(tip);
  wrap.querySelectorAll("path.tt-edge-hit, text.tt-count").forEach((elm) => {
    const i = Number(elm.getAttribute("data-ei"));
    const e = edges[i];
    if (!e || !byId[e.from] || !byId[e.to]) return;
    const label =
      `${byId[e.to].name} → ${byId[e.from].name} · 프록시 ${e.count}개` +
      (e.broken ? " · 끊김" : "") + " — 클릭: 저장소 목록";
    const vis = () => svg.querySelector(`path.tt-edge[data-ei="${i}"]`);
    elm.addEventListener("mousemove", (ev) => {
      const v = vis();
      if (v) v.classList.add("hover");
      tip.textContent = label;
      tip.style.display = "block";
      const wr = wrap.getBoundingClientRect();
      let left = ev.clientX - wr.left + wrap.scrollLeft + 12;
      if (left + tip.offsetWidth > wrap.scrollLeft + wr.width - 4) {
        left = ev.clientX - wr.left + wrap.scrollLeft - tip.offsetWidth - 12;
      }
      tip.style.left = `${Math.max(2, left)}px`;
      tip.style.top = `${Math.max(2, ev.clientY - wr.top - 30)}px`;
    });
    elm.addEventListener("mouseleave", () => {
      const v = vis();
      if (v) v.classList.remove("hover");
      tip.style.display = "none";
    });
    elm.addEventListener("click", () => showEdgeRepos(e));
  });
  wrap.querySelectorAll("g.tt-node").forEach((g) => {
    const id = g.getAttribute("data-id");
    let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;
    g.addEventListener("pointerdown", (ev) => {
      dragging = true; moved = false;
      const rect = svg.getBoundingClientRect();
      const scale = rect.width ? width / rect.width : 1;
      sx = ev.clientX * scale; sy = ev.clientY * scale;
      ox = pos[id].x; oy = pos[id].y;
      g.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    g.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const rect = svg.getBoundingClientRect();
      const scale = rect.width ? width / rect.width : 1;
      const dx = ev.clientX * scale - sx, dy = ev.clientY * scale - sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      const nx = Math.max(0, ox + dx), ny = Math.max(0, oy + dy);
      if (!Number.isFinite(nx) || !Number.isFinite(ny)) return;  // never go NaN
      pos[id].x = nx; pos[id].y = ny;
      g.setAttribute("transform", `translate(${pos[id].x},${pos[id].y})`);
      refreshEdges();
      growCanvas();
    });
    g.addEventListener("pointerup", () => {
      if (!dragging) return;
      dragging = false;
      if (moved) {
        let store = {};
        try { store = JSON.parse(localStorage.getItem("topoPos") || "{}"); } catch (e) { store = {}; }
        if (Number.isFinite(pos[id].x) && Number.isFinite(pos[id].y)) {
          store[id] = { x: Math.round(pos[id].x), y: Math.round(pos[id].y) };
          localStorage.setItem("topoPos", JSON.stringify(store));
        }
      } else {
        const n = byId[id];
        if (n) window.open(n.base_url, "_blank", "noopener,noreferrer");
      }
    });
  });
}

async function loadTopology() {
  const summary = document.getElementById("topo-summary");
  const body = document.getElementById("topo-body");
  summary.innerHTML = "";
  body.innerHTML = "";
  body.append(el("div", { class: "empty" }, "토폴로지를 분석하는 중…"));
  const probe = document.getElementById("topo-probe").checked;
  let data;
  try {
    data = await api(`/api/topology${probe ? "?probe=true" : ""}`);
  } catch (e) {
    body.innerHTML = "";
    body.append(el("div", { class: "empty" }, `토폴로지 조회 실패: ${e.message}`));
    return;
  }
  body.innerHTML = "";

  const down = data.nodes.filter((n) => !n.reachable).length;
  summary.append(
    summaryCard("노드", data.nodes.length.toLocaleString()),
    summaryCard("다운 노드", String(down)),
    summaryCard("끊긴 링크", String(data.broken_links))
  );

  if (!data.nodes.length) {
    body.append(el("div", { class: "empty" }, "노드가 없습니다."));
    return;
  }

  data.nodes.forEach((node) => {
    const statusBadge = !node.reachable
      ? el("span", { class: "badge down" }, "다운")
      : (node.error
          ? el("span", { class: "badge warn", title: node.error }, "권한?")
          : el("span", { class: "badge up" }, "정상"));
    const head = el("div", { class: "topo-node-head" }, [
      el("span", { class: "topo-node-name" }, node.name),
      statusBadge,
      el("span", { class: "url" }, node.base_url),
    ]);

    let detail;
    if (!node.reachable) {
      detail = el("div", { class: "site-error", style: "padding:6px 0" }, node.error || "연결 불가");
    } else if (!node.proxies.length) {
      detail = el("div", { class: "empty" }, "프록시 저장소 없음 (말단/호스트 노드)");
    } else {
      const rows = node.proxies.map((p) => {
        let targetCell;
        if (p.internal) {
          targetCell = el("td", {}, [
            el("span", { class: `badge ${p.broken ? "down" : "up"}` }, p.broken ? "끊김" : "연결"),
            " ",
            p.target_id || p.target_host,
          ]);
        } else {
          const mark = p.remote_reachable === false ? " ✗" : p.remote_reachable === true ? " ✓" : "";
          targetCell = el("td", {}, `외부: ${p.target_host}${mark}`);
        }
        return el("tr", { class: p.broken ? "differs" : "" }, [
          el("td", {}, p.repository),
          targetCell,
          el("td", { class: "url" }, p.remote_url),
        ]);
      });
      detail = buildTable(["프록시 저장소", "상위(부모)", "원격 주소"], rows);
    }

    body.append(el("div", { class: "topo-node" }, [head, detail]));
  });
}

// ---- comparison matrix ---------------------------------------------------

function cellDetail(c) {
  if (c.unknown) return "조회 불가 (인스턴스 응답 없음)";
  if (!c.present) return "이 인스턴스에 없음";
  const parts = [`포맷: ${c.format || "—"}`, `타입: ${c.type || "—"}`];
  if (c.remote_url) parts.push(`원격: ${c.remote_url}`);
  if (c.online === false) parts.push("상태: offline");
  return parts.join("\n");
}

function rowStatusBadge(status) {
  const map = {
    consistent: ["up", "일치"],
    drift: ["down", "설정 상이"],
    partial: ["warn", "일부 누락"],
    unknown: ["warn", "조회 불가"],
    no_ref: ["warn", "기준 서버에 없음"],
  };
  const [cls, label] = map[status] || ["warn", status];
  return el("span", { class: `badge ${cls} row-status` }, label);
}

function cellSignature(c) {
  const fields = (state.compareFields && state.compareFields.length)
    ? state.compareFields
    : ["format", "type", "remote_url"];
  return fields.map((f) => {
    if (f === "online") return c.online === false ? "offline" : "online";
    return c[f] || "";
  }).join("|");
}

// Human-readable value of a cell (format/type + proxy remote URL).
function cellValueText(c) {
  if (!c || !c.present) return "없음";
  const head = [c.format, c.type].filter(Boolean).join("/") || "설정";
  return c.remote_url ? `${head} · ${c.remote_url}` : head;
}

// The representative "reference" cell for a row: the chosen reference
// server's cell, or (auto mode) a cell with the majority configuration.
function referenceCell(row, columns, refId) {
  if (refId) {
    const rc = row.cells[refId];
    return rc && rc.present ? rc : null;
  }
  const present = columns.map((c) => row.cells[c.id]).filter((c) => c && c.present);
  if (!present.length) return null;
  const counts = {};
  present.forEach((c) => {
    const s = cellSignature(c);
    counts[s] = (counts[s] || 0) + 1;
  });
  let bestSig = null;
  let bestN = -1;
  Object.entries(counts).forEach(([s, n]) => {
    if (n > bestN) { bestN = n; bestSig = s; }
  });
  return present.find((c) => cellSignature(c) === bestSig) || null;
}

// Evaluate one row's status and per-cell match, either against the majority
// (server-computed, refId == "") or against a chosen reference server.
function evaluateRow(row, columns, refId) {
  const matches = {};
  if (!refId) {
    // Auto "majority" reference, recomputed over the *selected* columns so the
    // row status and cell ≠ marks reflect the current instance selection.
    const present = columns
      .map((col) => row.cells[col.id])
      .filter((c) => c && c.present);
    const reachable = columns.filter((col) => {
      const c = row.cells[col.id];
      return c && !c.unknown;
    });
    if (!present.length) {
      columns.forEach((col) => { matches[col.id] = null; });
      const status = reachable.length ? "partial" : "unknown";
      return { status, matches, refMissing: false };
    }
    // The majority reference is taken among non-slave cells; slave cells are
    // an intentional master/slave mirror and always count as matching.
    const nonSlave = present.filter((c) => !cellIsSlave(c));
    const counts = {};
    nonSlave.forEach((c) => {
      const s = cellSignature(c);
      counts[s] = (counts[s] || 0) + 1;
    });
    let majSig = null;
    let majN = -1;
    Object.entries(counts).forEach(([s, n]) => {
      if (n > majN) { majN = n; majSig = s; }
    });
    let anyDiff = false;
    columns.forEach((col) => {
      const c = row.cells[col.id];
      if (!c || !c.present) { matches[col.id] = null; return; }
      if (cellIsSlave(c)) {
        const sd = (state.slaveDiffCache || {})[`${col.id}:${row.repository}`];
        if (sd && sd.differs) { matches[col.id] = false; anyDiff = true; }
        else matches[col.id] = true;  // clean mirror (or not yet verified)
        return;
      }
      const m = cellSignature(c) === majSig;
      matches[col.id] = m;
      if (!m) anyDiff = true;
    });
    let status;
    if (anyDiff) status = "drift";
    else if (present.length < reachable.length) status = "partial";
    else status = "consistent";
    return { status, matches, refMissing: false };
  }

  const reachable = columns.filter((col) => {
    const c = row.cells[col.id];
    return c && !c.unknown;
  });
  const presentCount = columns.filter((col) => {
    const c = row.cells[col.id];
    return c && c.present;
  }).length;

  const refCell = row.cells[refId];
  if (!refCell || !refCell.present) {
    columns.forEach((col) => { matches[col.id] = null; });
    const status = refCell && refCell.unknown ? "unknown" : "no_ref";
    return { status, matches, refMissing: true };
  }

  const refSig = cellSignature(refCell);
  let anyDiff = false;
  columns.forEach((col) => {
    const c = row.cells[col.id];
    if (!c || !c.present) { matches[col.id] = null; return; }
    if (cellIsSlave(c)) {
      const sd = (state.slaveDiffCache || {})[`${col.id}:${row.repository}`];
      if (sd && sd.differs) { matches[col.id] = false; anyDiff = true; }
      else matches[col.id] = true;
      return;
    }
    const m = cellSignature(c) === refSig;
    matches[col.id] = m;
    if (!m) anyDiff = true;
  });

  let status;
  if (anyDiff) status = "drift";
  else if (presentCount < reachable.length) status = "partial";
  else status = "consistent";
  return { status, matches, refMissing: false };
}

// User-defined column (instance) order. Saved **server-side** so the same order
// loads on every browser/session; localStorage is a fast local fallback.
function loadMatrixColOrder() {
  if (Array.isArray(state.matrixColOrder)) return state.matrixColOrder;
  try { return JSON.parse(localStorage.getItem("matrixColOrder") || "[]"); }
  catch (e) { return []; }
}
function saveMatrixColOrder(ids) {
  state.matrixColOrder = ids;
  try { localStorage.setItem("matrixColOrder", JSON.stringify(ids)); } catch (e) { /* ignore */ }
  api("/api/instances/column-order", { method: "PUT", body: JSON.stringify({ order: ids }) })
    .catch(() => toast("순서 서버 저장 실패(로컬에는 저장됨)", "err"));
}
// Sort columns by the saved order; ids not in it keep their original order at
// the end (so newly added servers still appear).
function orderedMatrixColumns(cols) {
  const order = loadMatrixColOrder();
  if (!order.length) return cols.slice();
  const rank = {};
  order.forEach((id, i) => { rank[id] = i; });
  return cols.slice().sort((a, b) =>
    (rank[a.id] == null ? 1e9 : rank[a.id]) - (rank[b.id] == null ? 1e9 : rank[b.id]));
}
// Move srcId to sit just before beforeId in the full column order, then persist.
function reorderMatrixCol(srcId, beforeId) {
  if (!state.matrix) return;
  const ids = orderedMatrixColumns(state.matrix.columns).map((c) => c.id);
  const from = ids.indexOf(srcId);
  if (from < 0) return;
  ids.splice(from, 1);
  const to = ids.indexOf(beforeId);
  ids.splice(to < 0 ? ids.length : to, 0, srcId);
  saveMatrixColOrder(ids);
  renderMatrixPickers();
  renderMatrix();
}

function visibleMatrixColumns() {
  const m = state.matrix;
  if (!m) return [];
  const ordered = orderedMatrixColumns(m.columns);
  return state.matrixCols ? ordered.filter((c) => state.matrixCols.has(c.id)) : ordered;
}

function pruneMatrixSet(prev, all) {
  if (!prev) return new Set(all);
  const kept = all.filter((x) => prev.has(x));
  return new Set(kept.length ? kept : all);
}

function renderMatrixPickers() {
  const m = state.matrix;
  const instBox = document.getElementById("matrix-inst-pick");
  const repoBox = document.getElementById("matrix-repo-pick");
  if (!m || !instBox || !repoBox) return;
  instBox.innerHTML = "";
  orderedMatrixColumns(m.columns).forEach((col) => {
    const on = !state.matrixCols || state.matrixCols.has(col.id);
    const chip = el("button", {
      type: "button",
      class: `pick-chip ${on ? "on" : ""}`,
      draggable: "true",
      title: "클릭: 표시/숨김 · 드래그: 열 순서 변경",
      onclick: () => {
        if (chip._dragged) { chip._dragged = false; return; }
        toggleMatrixPick("matrixCols", col.id);
      },
    }, col.reachable ? col.name : `${col.name} ⚠`);
    chip.dataset.id = col.id;
    chip.addEventListener("dragstart", (e) => {
      chip._dragging = true; chip.classList.add("dragging");
      e.dataTransfer.setData("text/plain", col.id);
      e.dataTransfer.effectAllowed = "move";
    });
    chip.addEventListener("dragend", () => {
      chip._dragged = chip._dragging; chip._dragging = false;
      chip.classList.remove("dragging");
    });
    chip.addEventListener("dragover", (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; });
    chip.addEventListener("drop", (e) => {
      e.preventDefault();
      const src = e.dataTransfer.getData("text/plain");
      if (src && src !== col.id) reorderMatrixCol(src, col.id);
    });
    instBox.append(chip);
  });
  repoBox.innerHTML = "";
  const q = (state.matrixRepoSearch || "").trim().toLowerCase();
  let shown = 0;
  m.rows.forEach((r) => {
    if (q && !r.repository.toLowerCase().includes(q)) return;
    shown++;
    const on = !state.matrixRepos || state.matrixRepos.has(r.repository);
    repoBox.append(el("button", {
      type: "button",
      class: `pick-chip ${on ? "on" : ""}${q ? " hit" : ""}`,
      onclick: () => toggleMatrixPick("matrixRepos", r.repository),
    }, r.repository));
  });
  if (q && !shown) {
    repoBox.append(el("span", { class: "pick-empty" }, `'${q}'에 맞는 저장소가 없습니다.`));
  }
  const total = m.rows.length;
  const selected = state.matrixRepos ? state.matrixRepos.size : total;
  const countEl = document.getElementById("matrix-repo-count");
  if (countEl) {
    countEl.textContent = q
      ? `표시 ${shown} · 선택 ${selected}/${total}`
      : `선택 ${selected}/${total}`;
  }
}

// Repos currently matching the search box (all repos when the box is empty).
function filteredMatrixRepos() {
  const m = state.matrix;
  if (!m) return [];
  const q = (state.matrixRepoSearch || "").trim().toLowerCase();
  return m.rows
    .map((r) => r.repository)
    .filter((name) => !q || name.toLowerCase().includes(q));
}

function toggleMatrixPick(key, id) {
  const m = state.matrix;
  if (!m) return;
  const all = key === "matrixCols" ? m.columns.map((c) => c.id) : m.rows.map((r) => r.repository);
  const set = state[key] ? new Set(state[key]) : new Set(all);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  state[key] = set;
  populateMatrixRef();
  renderMatrixPickers();
  renderMatrix();
}

function setAllMatrixRepos(on) {
  const m = state.matrix;
  if (!m) return;
  // Scope 전체/해제 to the current search: with a query, only the matching
  // repos are turned on/off so you can e.g. "yum → 전체" select just those.
  const all = m.rows.map((r) => r.repository);
  const scope = filteredMatrixRepos();
  const cur = new Set(state.matrixRepos || all);
  scope.forEach((name) => { if (on) cur.add(name); else cur.delete(name); });
  state.matrixRepos = cur;
  renderMatrixPickers();
  renderMatrix();
}

function matrixColName(id) {
  const m = state.matrix;
  const c = m && m.columns.find((x) => x.id === id);
  return c ? c.name : id;
}

function instBaseUrl(id) {
  const i = (state.instances || []).find((x) => x.id === id);
  return i ? (i.base_url || "") : "";
}

// URL of a server's Nexus admin page for a repository (used by the popup).
function adminRepoUrl(instId, repo) {
  const base = instBaseUrl(instId);
  if (!base) return "";
  return `${base.replace(/\/+$/, "")}/#admin/repository/repositories:${encodeURIComponent(repo)}`;
}

// --- Rich hover card showing a repository's full configuration -------------

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));
}

function matrixTip() {
  let t = document.getElementById("mtip");
  if (!t) {
    t = el("div", { id: "mtip", class: "mtip hidden" });
    document.body.append(t);
  }
  return t;
}

function positionMatrixTip(x, y) {
  const t = matrixTip();
  const pad = 14;
  const r = t.getBoundingClientRect();
  let left = x + pad;
  let top = y + pad;
  if (left + r.width > window.innerWidth - 8) left = x - r.width - pad;
  if (top + r.height > window.innerHeight - 8) top = y - r.height - pad;
  t.style.left = `${Math.max(8, left)}px`;
  t.style.top = `${Math.max(8, top)}px`;
}

function showMatrixTip(html, x, y) {
  const t = matrixTip();
  t.innerHTML = html;
  t.classList.remove("hidden");
  positionMatrixTip(x, y);
}

function hideMatrixTip() {
  matrixTip().classList.add("hidden");
}

// Flatten a (possibly nested) config object into "a.b.c: value" lines so the
// hover card can show everything about the repository.
function flattenConfig(obj, prefix, out) {
  Object.entries(obj).forEach(([k, v]) => {
    if (k === "password") return;
    const key = prefix ? `${prefix}.${k}` : k;
    if (v === null || v === undefined || v === "") return;
    if (Array.isArray(v)) {
      if (v.length) out.push(`${key}: ${v.join(", ")}`);
    } else if (typeof v === "object") {
      flattenConfig(v, key, out);
    } else {
      out.push(`${key}: ${v}`);
    }
  });
  return out;
}

function renderCfgTip(repo, instName, cfg, slaveHtml) {
  const header =
    `<b>${escapeHtml(repo)}</b> <span class="mtip-sub">@ ${escapeHtml(instName)}` +
    ` · ${escapeHtml(cfg.format || "—")}/${escapeHtml(cfg.type || "—")}</span>`;
  const skip = new Set(["name", "format", "type", "url"]);
  const flat = [];
  Object.entries(cfg).forEach(([k, v]) => {
    if (!skip.has(k)) flattenConfig({ [k]: v }, "", flat);
  });
  if (cfg.url) flat.unshift(`url: ${cfg.url}`);
  const body = flat.length ? flat.map(escapeHtml).join("<br>") : "(추가 설정 없음)";
  return `${header}${slaveHtml || ""}<hr>${body}`;
}

function updateMatrixTip(html) {
  const t = matrixTip();
  if (!t.classList.contains("hidden")) t.innerHTML = html;
}

function hostOf(u) {
  try {
    const url = new URL(/^[a-zA-Z]+:\/\//.test(u) ? u : `http://${u}`);
    return url.hostname.toLowerCase();
  } catch (_) { return ""; }
}

function repoNameFromRemote(u) {
  const m = /\/repository\/([^/]+)/.exec(u || "");
  return m ? decodeURIComponent(m[1]) : "";
}

// Hostnames an instance answers to: base_url plus the optional alt_url
// (보조 주소). Proxies may point at a master by IP or by FQDN — matching
// either one means "same server".
function instHosts(i) {
  return [hostOf(i.base_url || ""), hostOf(i.alt_url || "")].filter(Boolean);
}

// A "slave" cell is a proxy whose remote URL points at one of our managed
// servers (its master). Such a cell is the expected master/slave setup, not a
// configuration drift, so it is treated as normal in the matrix.
function cellIsSlave(c) {
  if (!c || !c.remote_url) return false;
  const h = hostOf(c.remote_url);
  return !!h && (state.instances || []).some((i) => instHosts(i).includes(h));
}

function masterNameForCell(c) {
  const h = c && c.remote_url ? hostOf(c.remote_url) : "";
  const m = h && (state.instances || []).find((i) => instHosts(i).includes(h));
  return m ? m.name : "";
}

// Keys (with both values) that differ between two repo configs, ignoring
// host-specific fields. Empty = identical apart from those (clean mirror).
function configDiffKeys(a, b) {
  const norm = (cfg) => {
    const out = [];
    flattenConfig(cfg, "", out);
    const map = {};
    out.forEach((l) => {
      const i = l.indexOf(": ");
      const k = l.slice(0, i);
      if (k === "proxy.remoteUrl" || k === "url" || k === "name") return;
      map[k] = l.slice(i + 2);
    });
    return map;
  };
  const ma = norm(a);
  const mb = norm(b);
  const keys = new Set([...Object.keys(ma), ...Object.keys(mb)]);
  const diffs = [];
  keys.forEach((k) => { if (ma[k] !== mb[k]) diffs.push({ key: k, a: ma[k], b: mb[k] }); });
  diffs.sort((x, y) => (x.key < y.key ? -1 : 1));
  return diffs;
}

// Resolve (and cache) a slave cell's relationship to its master: which master,
// which repo, and whether anything beyond remoteUrl differs (with the keys).
async function ensureSlaveInfo(repo, col, c) {
  const key = `${col.id}:${repo}`;
  state.slaveDiffCache = state.slaveDiffCache || {};
  if (key in state.slaveDiffCache) return state.slaveDiffCache[key];
  const h = c && c.remote_url ? hostOf(c.remote_url) : "";
  const master = h
    ? (state.instances || []).find((i) => i.id !== col.id && instHosts(i).includes(h))
    : null;
  if (!master) { state.slaveDiffCache[key] = { master: null }; return state.slaveDiffCache[key]; }
  const mRepo = repoNameFromRemote(c.remote_url) || repo;
  let entry = { master, mRepo, differs: false, keys: [], unverified: true };
  try {
    state.repoCfgCache = state.repoCfgCache || {};
    let myCfg = state.repoCfgCache[key];
    if (!myCfg) {
      myCfg = await api(
        `/api/instances/${encodeURIComponent(col.id)}/repository-config` +
          `?repository=${encodeURIComponent(repo)}` +
          `&format=${encodeURIComponent(c.format || "")}&type=${encodeURIComponent(c.type || "")}`
      );
      state.repoCfgCache[key] = myCfg;
    }
    const mKey = `${master.id}:${mRepo}`;
    let mCfg = state.repoCfgCache[mKey];
    if (!mCfg) {
      mCfg = await api(
        `/api/instances/${encodeURIComponent(master.id)}/repository-config-by-name` +
          `?repository=${encodeURIComponent(mRepo)}`
      );
      state.repoCfgCache[mKey] = mCfg;
    }
    const diffs = configDiffKeys(myCfg, mCfg);
    entry = { master, mRepo, differs: diffs.length > 0, keys: diffs, unverified: false };
  } catch (_) {
    /* keep unverified entry */
  }
  state.slaveDiffCache[key] = entry;
  return entry;
}

// Detect whether a proxy repo points at another *managed* server (its master)
// and, if so, annotate the hover card with a "<master> Slave" badge.
async function detectSlave(repo, col, cfg, key) {
  state.slaveCache = state.slaveCache || {};
  const cLike = {
    remote_url: cfg.proxy && cfg.proxy.remoteUrl,
    format: cfg.format,
    type: cfg.type,
  };
  const info = await ensureSlaveInfo(repo, col, cLike);
  if (!info || !info.master) { state.slaveCache[key] = ""; return; }

  let cls = "";
  let tag = "Slave";
  let sub = `→ ${escapeHtml(info.mRepo)}`;
  let extra = "";
  if (info.unverified) {
    sub += " · 마스터 설정 확인 불가";
  } else if (info.differs) {
    cls = "diff";
    tag = "Slave · 설정 다름";
    const rows = (info.keys || []).map((d) =>
      `<tr><td>${escapeHtml(d.key)}</td>` +
      `<td>${escapeHtml(d.a == null ? "(없음)" : d.a)}</td>` +
      `<td>${escapeHtml(d.b == null ? "(없음)" : d.b)}</td></tr>`
    ).join("");
    extra =
      `<table class="mtip-difftable">` +
      `<tr><th>항목</th><th>이 서버</th><th>마스터</th></tr>${rows}</table>`;
  } else {
    sub += " · 설정 동일 (remoteUrl만 다름)";
  }
  const note =
    `<div class="mtip-slave ${cls}">` +
    `<div class="mtip-slave-name">⛓ ${escapeHtml(info.master.name)}</div>` +
    `<div class="mtip-slave-tag">${tag}</div>` +
    `<div class="mtip-sub">${sub}</div>${extra}</div>`;
  state.slaveCache[key] = note;
  if (state.matrixHoverKey === key) {
    updateMatrixTip(renderCfgTip(repo, col.name, cfg, note));
  }
}

async function onMatrixCellHover(e, repo, col, c) {
  const x = e.clientX;
  const y = e.clientY;
  const key = `${col.id}:${repo}`;
  if (c.unknown) {
    showMatrixTip(`<b>${escapeHtml(repo)}</b><hr>조회 불가 (인스턴스 응답 없음)`, x, y);
    return;
  }
  if (!c.present) {
    showMatrixTip(`<b>${escapeHtml(repo)}</b> <span class="mtip-sub">@ ${escapeHtml(col.name)}</span><hr>이 인스턴스에 없음`, x, y);
    return;
  }
  state.repoCfgCache = state.repoCfgCache || {};
  state.slaveCache = state.slaveCache || {};
  if (state.repoCfgCache[key]) {
    const cfg = state.repoCfgCache[key];
    showMatrixTip(renderCfgTip(repo, col.name, cfg, state.slaveCache[key]), x, y);
    if (!(key in state.slaveCache)) detectSlave(repo, col, cfg, key);
    return;
  }
  const base =
    `<b>${escapeHtml(repo)}</b> <span class="mtip-sub">@ ${escapeHtml(col.name)} · ` +
    `${escapeHtml(c.format || "—")}/${escapeHtml(c.type || "—")}</span><hr>`;
  showMatrixTip(`${base}<span class="mtip-sub">전체 설정 불러오는 중…</span>`, x, y);
  try {
    const cfg = await api(
      `/api/instances/${encodeURIComponent(col.id)}/repository-config` +
        `?repository=${encodeURIComponent(repo)}` +
        `&format=${encodeURIComponent(c.format || "")}&type=${encodeURIComponent(c.type || "")}`
    );
    state.repoCfgCache[key] = cfg;
    if (state.matrixHoverKey === key) showMatrixTip(renderCfgTip(repo, col.name, cfg), x, y);
    detectSlave(repo, col, cfg, key);
  } catch (err) {
    if (state.matrixHoverKey === key) {
      showMatrixTip(`${base}<span class="mtip-sub">설정 조회 실패: ${escapeHtml(err.message)}</span>`, x, y);
    }
  }
}

// Drag a present (green/≠) cell onto another cell in the SAME repository row
// to copy that repo's config from the source instance to the target.
function onMatrixDragStart(e, repo, inst, present) {
  if (!present) { e.preventDefault(); return; }
  state.matrixDrag = { repo, inst };
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = "copy";
    try { e.dataTransfer.setData("text/plain", `${repo}@${inst}`); } catch (_) {}
  }
}

// Stepped progress popup (also used as the completion popup). Closing it does
// not cancel the in-flight request — the copy keeps going and a toast still
// fires on completion.
function openStepModal(title, steps, sub) {
  const stepEls = steps.map((s) => {
    const icon = el("span", { class: "step-ic" }, "○");
    return { icon, row: el("div", { class: "step-row" }, [icon, el("span", {}, s)]) };
  });
  const note = el("p", { class: "hint bulk-bg-note" },
    "ℹ 이 팝업을 닫아도 작업은 계속 진행되며, 완료되면 알림으로 알려드립니다. (브라우저 탭을 닫으면 화면 표시만 사라집니다)");
  const closeBtn = el("button", { type: "button", class: "modal-x", title: "닫기(백그라운드 계속)" }, "✕");
  const okBtn = el("button", { type: "button", class: "hidden", style: "margin-top:8px" }, "확인");
  const overlay = el("div", { class: "modal" }, [
    el("div", { class: "modal-box", style: "max-width:460px" }, [
      el("div", { class: "modal-head" }, [el("h3", {}, title), closeBtn]),
      el("div", { class: "modal-body" }, [
        sub ? el("p", { class: "hint", style: "margin:8px 0 4px" }, sub) : null,
        el("div", { class: "step-list" }, stepEls.map((s) => s.row)),
        note, okBtn,
      ]),
    ]),
  ]);
  const close = () => overlay.remove();
  closeBtn.addEventListener("click", close);
  okBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.body.append(overlay);
  return {
    setStep(idx) {
      stepEls.forEach((s, i) => {
        s.icon.textContent = i < idx ? "✓" : (i === idx ? "⏳" : "○");
        s.icon.className = "step-ic" + (i < idx ? " done" : i === idx ? " active" : "");
      });
    },
    finish(ok, message) {
      stepEls.forEach((s) => { if (ok) { s.icon.textContent = "✓"; s.icon.className = "step-ic done"; } });
      note.textContent = (ok ? "✅ " : "❌ ") + message;
      note.className = "hint bulk-bg-note " + (ok ? "bulk-bg-done" : "bulk-bg-fail");
      okBtn.classList.remove("hidden");
    },
  };
}

async function onMatrixDrop(e, repo, inst) {
  e.preventDefault();
  e.currentTarget.classList.remove("drop-hover");
  const src = state.matrixDrag;
  state.matrixDrag = null;
  if (!src) return;
  if (src.repo !== repo) {
    toast("같은 저장소(같은 이름) 행으로만 복사할 수 있습니다.", "err");
    return;
  }
  if (src.inst === inst) return;
  const sName = matrixColName(src.inst);
  const tName = matrixColName(inst);
  if (!confirm(
    `'${tName}'의 '${repo}' 설정을 '${sName}' 기준으로 덮어써서 설정을 업데이트 하시겠습니까?\n\n` +
    `원본: ${sName}\n대상: ${tName}\n(대상에 '${repo}'가 없으면 새로 생성됩니다.\n` +
    `그룹 저장소이면 대상에 없는 멤버 저장소도 함께 생성됩니다.)`
  )) return;

  const steps = [
    `원본 서버(${sName})에 접속합니다`,
    `원본의 '${repo}' 설정을 읽습니다`,
    `대상 서버(${tName})에 연결합니다`,
    `설정을 복사(적용)합니다`,
    `완료합니다`,
  ];
  const M = openStepModal(`설정 복사 — ${sName} → ${tName}`, steps, `저장소: ${repo}`);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    M.setStep(0);
    const apiP = api(
      `/api/matrix/copy-repo?repository=${encodeURIComponent(repo)}` +
        `&source_id=${encodeURIComponent(src.inst)}&target_id=${encodeURIComponent(inst)}`,
      { method: "POST" }
    );
    // Walk the user through what the server is doing while the request flies.
    await sleep(250); M.setStep(1);
    await sleep(250); M.setStep(2);
    await sleep(250); M.setStep(3);
    const r = await apiP;
    const it = (r.items && r.items[0]) || {};
    if (it.status === "fail") {
      M.finish(false, `복사 실패: ${it.detail || "원인 불명"}`);
      toast(`복사 실패: ${it.detail || "원인 불명"}`, "err");
    } else {
      M.setStep(5);
      const msg = `'${repo}' 복사 완료 — ${it.status === "update" ? "갱신" : "생성"} (${tName})`;
      M.finish(true, msg);
      toast(msg);
    }
    await loadMatrix();
  } catch (err) {
    M.finish(false, `복사 실패: ${err.message}`);
    toast(`복사 실패: ${err.message}`, "err");
  }
}

function renderMatrix() {
  const container = document.getElementById("matrix-table");
  container.innerHTML = "";
  const matrix = state.matrix;
  if (!matrix) return;
  if (!matrix.columns.length) {
    container.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다."));
    return;
  }

  // Only the user-selected instances form the comparison (drift is recomputed
  // over this subset), and only the selected repositories are listed.
  const columns = visibleMatrixColumns();
  if (!columns.length) {
    container.append(el("div", { class: "empty" }, "비교할 인스턴스를 1개 이상 선택하세요."));
    return;
  }
  const refId = columns.some((c) => c.id === state.matrixReference) ? state.matrixReference : "";
  const evals = new Map();
  matrix.rows.forEach((r) => evals.set(r, evaluateRow(r, columns, refId)));

  const driftOnly = document.getElementById("drift-only").checked;
  let rows = state.matrixRepos
    ? matrix.rows.filter((r) => state.matrixRepos.has(r.repository))
    : matrix.rows;
  if (driftOnly) rows = rows.filter((r) => evals.get(r).status !== "consistent");

  if (!rows.length) {
    container.append(el("div", { class: "empty" },
      driftOnly ? "차이가 있는 저장소가 없습니다. 모두 일치합니다 ✓" : "표시할 저장소가 없습니다."));
    return;
  }

  // Header: blank corner + one column per instance (with unreachable mark).
  const headCells = [el("th", { class: "rowhead" }, "저장소 \\ 인스턴스")];
  columns.forEach((col) => {
    let label = col.reachable ? col.name : `${col.name} ⚠`;
    if (col.id === refId) label = `${label} (기준)`;
    const base = instBaseUrl(col.id);
    const labelNode = base
      ? el("a", {
          class: "col-link",
          href: base,
          target: "_blank",
          rel: "noopener noreferrer",
          draggable: "false",   // let the <th> own the drag for reordering
          title: `새 탭에서 ${col.name} Nexus 열기`,
        }, label)
      : label;
    // Drag a column header onto another to reorder; saved server-side.
    headCells.push(el("th", {
      class: (col.id === refId ? "ref-col " : "") + "matrix-col-head",
      title: (col.error || col.name) + " · 헤더를 드래그해 순서 변경",
      draggable: "true",
      ondragstart: (e) => { e.dataTransfer.setData("text/plain", col.id); e.dataTransfer.effectAllowed = "move"; },
      ondragover: (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; e.currentTarget.classList.add("col-drop"); },
      ondragleave: (e) => e.currentTarget.classList.remove("col-drop"),
      ondrop: (e) => {
        e.preventDefault();
        e.currentTarget.classList.remove("col-drop");
        const src = e.dataTransfer.getData("text/plain");
        if (src && src !== col.id) reorderMatrixCol(src, col.id);
      },
    }, labelNode));
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const body = rows.map((row) => {
    const ev = evals.get(row);
    const refCell = referenceCell(row, columns, refId);
    const refLabel = refId
      ? ((columns.find((c) => c.id === refId) || {}).name || "기준")
      : "다수 기준";
    const tds = [
      el("td", { class: "rowhead" }, [
        el("span", { class: "link", title: "설정 자세히 비교", onclick: () => openRepoDiff(row.repository) }, row.repository),
        rowStatusBadge(ev.status),
      ]),
    ];
    columns.forEach((col) => {
      const c = row.cells[col.id] || { present: false };
      const match = ev.matches[col.id];
      let cls, mark, meta;
      if (c.unknown) { cls = "unknown"; mark = "?"; meta = ""; }
      else if (!c.present) { cls = "missing"; mark = "—"; meta = ""; }
      else if (match === null) { cls = "neutral"; mark = "•"; meta = c.format || ""; }
      else if (match) { cls = "consistent"; mark = "✓"; meta = c.format || ""; }
      else { cls = "drift"; mark = "≠"; meta = [c.type, c.remote_url].filter(Boolean).join(" · ") || c.format || ""; }

      const refMark = col.id === refId ? "ref-col" : "";
      const present = !!c.present && !c.unknown;
      // A slave (proxy → managed master) is the expected setup. If only the
      // remoteUrl differs it is normal (✓); if other settings differ it is a
      // real drift (≠). The "Slave" tag is rendered as a readable badge.
      let metaNode = meta ? el("span", { class: "meta" }, meta) : null;
      if (present && cellIsSlave(c)) {
        const mn = masterNameForCell(c);
        const sd = (state.slaveDiffCache || {})[`${col.id}:${row.repository}`];
        const differs = !!(sd && sd.differs);
        if (differs) { cls = "drift"; mark = "≠"; }
        else { cls = "consistent"; mark = "✓"; }
        metaNode = el("span", { class: `slave-tag-cell ${differs ? "diff" : ""}` }, [
          mn ? el("span", { class: "slave-master" }, mn) : null,
          el("span", { class: "slave-badge" }, differs ? "Slave · 다름" : "Slave"),
          sd && sd.unverified ? el("span", { class: "slave-master" }, "?") : null,
        ]);
      }
      const inner = el("span", { class: `mcell ${cls}` }, [
        el("span", { class: "mark" }, mark),
        metaNode,
      ]);
      const cell = c;
      const td = el("td", {
        class: `mdrop ${refMark}${present ? " clickable" : ""}`,
        draggable: present ? "true" : "false",
        onclick: present ? () => openRepoDiff(row.repository) : null,
        ondragstart: (e) => onMatrixDragStart(e, row.repository, col.id, present),
        ondragover: (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; },
        ondragenter: (e) => e.currentTarget.classList.add("drop-hover"),
        ondragleave: (e) => e.currentTarget.classList.remove("drop-hover"),
        ondrop: (e) => onMatrixDrop(e, row.repository, col.id),
        onmouseenter: (e) => { state.matrixHoverKey = `${col.id}:${row.repository}`; onMatrixCellHover(e, row.repository, col, cell); },
        onmousemove: (e) => { if (state.matrixHoverKey === `${col.id}:${row.repository}`) positionMatrixTip(e.clientX, e.clientY); },
        onmouseleave: () => { state.matrixHoverKey = null; hideMatrixTip(); },
      }, inner);
      tds.push(td);
    });
    return el("tr", {}, tds);
  });

  const table = el("table", { class: "matrix" }, [thead, el("tbody", {}, body)]);
  container.append(table);

  // Lazily verify slave cells' deep config (remoteUrl aside) and re-render once
  // resolved, so cells/rows reflect real differences instead of assuming clean.
  const toVerify = [];
  rows.forEach((row) => {
    columns.forEach((col) => {
      const c = row.cells[col.id];
      if (c && c.present && !c.unknown && cellIsSlave(c)) {
        const k = `${col.id}:${row.repository}`;
        if (!(state.slaveDiffCache && k in state.slaveDiffCache)) {
          toVerify.push({ repo: row.repository, col, c });
        }
      }
    });
  });
  if (toVerify.length && !state.slaveVerifying) {
    state.slaveVerifying = true;
    Promise.allSettled(toVerify.map((v) => ensureSlaveInfo(v.repo, v.col, v.c)))
      .then(() => { state.slaveVerifying = false; renderMatrix(); });
  }
}

function populateMatrixRef() {
  const sel = document.getElementById("matrix-ref");
  // Default to the designated reference server (from 서버 설정), if any.
  const designated = (state.instances.find((i) => i.is_reference) || {}).id || "";
  const prev = state.matrixReference || designated || "";
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "(자동: 다수 기준)"));
  // The reference must be one of the currently selected instances.
  visibleMatrixColumns().forEach((col) =>
    sel.append(el("option", { value: col.id }, col.name))
  );
  sel.value = [...sel.options].some((o) => o.value === prev) ? prev : "";
  state.matrixReference = sel.value;
}

async function loadMatrix() {
  const container = document.getElementById("matrix-table");
  try {
    const [matrix, cf, ord] = await Promise.all([
      api("/api/matrix"),
      api("/api/instances/compare-fields"),
      api("/api/instances/column-order").catch(() => ({ order: [] })),
    ]);
    state.matrix = matrix;
    state.compareFields = (cf && cf.fields) || [];
    state.matrixColOrder = (ord && ord.order) || [];   // server-saved column order
    // A fresh matrix load means server configs may have changed — drop the
    // derived caches so hover tooltips/badges don't show stale slave-diff info.
    state.slaveDiffCache = {};
    state.repoCfgCache = {};
    state.slaveCache = {};
    // Keep prior selection across reloads; default to all when first seen.
    state.matrixCols = pruneMatrixSet(state.matrixCols, matrix.columns.map((c) => c.id));
    state.matrixRepos = pruneMatrixSet(state.matrixRepos, matrix.rows.map((r) => r.repository));
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `매트릭스 로드 실패: ${e.message}`));
    return;
  }
  renderMatrixPickers();
  populateMatrixRef();
  renderMatrix();
}

document.getElementById("drift-only").addEventListener("change", renderMatrix);
// Scrolling the table hides the legend/description (more room); back to top shows it.
(() => {
  const wrap = document.getElementById("matrix-table");
  const sec = document.getElementById("matrix");
  if (wrap && sec) wrap.addEventListener("scroll", () => {
    sec.classList.toggle("matrix-scrolled", wrap.scrollTop > 4);
  });
})();
document.getElementById("matrix-ref").addEventListener("change", (e) => {
  state.matrixReference = e.target.value;
  renderMatrix();
});
document.getElementById("matrix-repo-all").addEventListener("click", () => setAllMatrixRepos(true));
document.getElementById("matrix-repo-none").addEventListener("click", () => setAllMatrixRepos(false));
document.getElementById("matrix-col-reset").addEventListener("click", () => {
  localStorage.removeItem("matrixColOrder");
  state.matrixColOrder = [];
  api("/api/instances/column-order", { method: "PUT", body: JSON.stringify({ order: [] }) }).catch(() => {});
  toast("열 순서를 기본값으로 되돌렸습니다");
  renderMatrixPickers();
  renderMatrix();
});
document.getElementById("matrix-repo-search").addEventListener("input", (ev) => {
  state.matrixRepoSearch = ev.target.value;
  renderMatrixPickers();   // filter chips only; the matrix table is unaffected
});

// ---- repository config diff (deep comparison) ----------------------------

// Build a field-by-field diff table element (shared by modal and compare tab).
function diffTable(diff, diffOnly) {
  let fields = diff.fields;
  if (diffOnly) fields = fields.filter((f) => f.differs);

  if (!fields.length) {
    return el("div", { class: "empty" },
      diffOnly ? "모든 설정이 동일합니다 ✓" : "비교할 설정 항목이 없습니다.");
  }

  const headCells = [el("th", {}, "설정 항목")];
  diff.columns.forEach((col) => {
    const label = col.reachable ? col.name : `${col.name} ⚠`;
    const url = adminRepoUrl(col.id, diff.repository);
    const node = url
      ? el("a", {
          class: "col-link", href: url, target: "_blank", rel: "noopener noreferrer",
          title: `${col.name}의 admin 저장소 설정 열기`,
        }, label)
      : label;
    headCells.push(el("th", { title: col.error || col.name }, node));
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const rows = fields.map((f) => {
    const tds = [el("td", { class: "key" }, f.key)];
    diff.columns.forEach((col) => {
      const v = f.values[col.id];
      if (!col.reachable) tds.push(el("td", { class: "unreach" }, "조회 불가"));
      else if (v === null || v === undefined) tds.push(el("td", { class: "missing" }, "(없음)"));
      else tds.push(el("td", {}, v === "" ? "(빈 값)" : v));
    });
    return el("tr", { class: f.differs ? "differs" : "" }, tds);
  });

  return el("table", { class: "diff" }, [thead, el("tbody", {}, rows)]);
}

function renderRepoDiff() {
  const body = document.getElementById("repo-modal-body");
  body.innerHTML = "";
  if (!state.repoDiff) return;
  body.append(diffTable(state.repoDiff, document.getElementById("repo-diff-only").checked));
  const open = repoOpenPanel();
  if (open) body.append(open);
  const sync = repoSlaveSyncPanel();
  if (sync) body.append(sync);
  body.append(repoBulkPanel());
  body.append(repoCacheSyncPanel());
}

// Apply one server's repo config to several other servers at once.
function repoBulkPanel() {
  const repo = state.repoDiffName;
  const cols = (state.repoDiff && state.repoDiff.columns) || [];
  if (cols.length < 2) return el("div", {});
  const src = el("select", { id: "bulk-src" }, cols.map((c) => el("option", { value: c.id }, c.name)));
  const targetBox = el("div", { class: "bulk-tgt-grid", id: "bulk-targets" });
  const renderTargets = () => {
    targetBox.innerHTML = "";
    cols.forEach((c) => {
      if (c.id === src.value) return;
      // Name on top, checkbox underneath — so it's unambiguous which box
      // belongs to which server. Clicking the whole cell toggles it.
      const cb = el("input", { type: "checkbox", class: "bulk-tgt", "data-id": c.id });
      targetBox.append(el("label", { class: "bulk-tgt-cell" }, [
        el("span", { class: "bulk-tgt-name" }, c.name),
        cb,
      ]));
    });
  };
  src.addEventListener("change", renderTargets);
  renderTargets();
  const status = el("span", { class: "hint", style: "margin:0" });
  const btn = el("button", {
    type: "button",
    onclick: () => runBulkPush(repo, src, status),
  }, "선택 서버에 적용");
  return el("div", { class: "settings-card", style: "margin-top:14px" }, [
    el("h3", {}, "일괄 적용 (여러 서버에 설정 복사)"),
    el("p", { class: "hint" },
      "원본 서버의 이 저장소 설정을 선택한 서버들에 한 번에 적용(덮어쓰기·없으면 생성)합니다. 그룹이면 누락 멤버도 함께 생성됩니다."),
    el("div", { class: "form-actions", style: "justify-content:flex-start;gap:10px;align-items:flex-start;flex-wrap:wrap" }, [
      el("label", { class: "ref-pick" }, ["원본 ", src]),
      el("label", { class: "ref-pick", style: "align-items:flex-start" }, ["대상 ", targetBox]),
      btn, status,
    ]),
  ]);
}

// Big progress popup for bulk apply. Closing it does NOT stop the job — the
// loop keeps running in this browser tab (updating detached nodes is harmless).
function openBulkModal(sName, repo, targetCols) {
  const big = el("div", { class: "bulk-big" }, `0 / ${targetCols.length}`);
  const fill = el("div", { class: "bulk-bar-fill" });
  const rowEls = {};
  const rowsBox = el("div", { class: "bulk-rows" });
  targetCols.forEach((t) => {
    const badge = el("span", { class: "badge", style: "background:var(--panel-2)" }, "대기");
    rowEls[t.id] = badge;
    rowsBox.append(el("div", { class: "bulk-row" }, [el("span", {}, t.name), badge]));
  });
  const closeBtn = el("button", { type: "button", class: "modal-x", title: "닫기(백그라운드 계속)" }, "✕");
  const overlay = el("div", { class: "modal" }, [
    el("div", { class: "modal-box", style: "max-width:520px" }, [
      el("div", { class: "modal-head" }, [el("h3", {}, "일괄 적용 진행"), closeBtn]),
      el("div", { class: "modal-body" }, [
        big,
        el("div", { class: "bulk-bar" }, fill),
        el("p", { class: "hint bulk-bg-note" },
          "ℹ 이 팝업을 닫아도 현재 브라우저 탭에서 백그라운드로 계속 진행됩니다. 단, 브라우저 탭/창을 닫으면 중단됩니다."),
        el("p", { class: "hint", style: "margin:4px 0 8px" }, `원본 ${sName} · 저장소 ${repo}`),
        rowsBox,
      ]),
    ]),
  ]);
  closeBtn.addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.append(overlay);
  return { overlay, big, fill, rowEls, note: overlay.querySelector(".bulk-bg-note") };
}

async function runBulkPush(repo, srcSel, status) {
  const sourceId = srcSel.value;
  const sName = srcSel.options[srcSel.selectedIndex].text;
  const checked = [...document.querySelectorAll(".bulk-tgt:checked")];
  const targets = checked.map((c) => c.getAttribute("data-id"));
  if (!targets.length) { toast("적용할 대상 서버를 선택하세요.", "err"); return; }
  const nameOf = (cb) => {
    const cell = cb.closest(".bulk-tgt-cell");
    const n = cell && cell.querySelector(".bulk-tgt-name");
    return n ? n.textContent : cb.getAttribute("data-id");
  };
  const targetCols = checked.map((c) => ({ id: c.getAttribute("data-id"), name: nameOf(c) }));
  if (!confirm(
    `'${sName}'의 '${repo}' 설정을 ${targets.length}개 서버에 적용(덮어쓰기·없으면 생성)합니다.\n진행할까요?`
  )) return;

  const M = openBulkModal(sName, repo, targetCols);
  let ok = 0, fail = 0;
  for (let i = 0; i < targets.length; i++) {
    const badge = M.rowEls[targets[i]];
    if (badge) { badge.textContent = "진행 중…"; badge.className = "badge warn"; }
    status.textContent = `적용 중… ${i + 1}/${targets.length}`;
    M.big.textContent = `${i} / ${targets.length}`;
    M.fill.style.width = `${Math.round((i / targets.length) * 100)}%`;
    try {
      const r = await api(
        `/api/matrix/copy-repo?repository=${encodeURIComponent(repo)}` +
          `&source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targets[i])}`,
        { method: "POST" }
      );
      const it = (r.items && r.items[0]) || {};
      if (it.status === "fail") { fail++; if (badge) { badge.textContent = "실패"; badge.className = "badge down"; badge.title = it.detail || ""; } }
      else { ok++; if (badge) { badge.textContent = "성공"; badge.className = "badge up"; } }
    } catch (e) { fail++; if (badge) { badge.textContent = "실패"; badge.className = "badge down"; badge.title = e.message || ""; } }
  }
  M.big.textContent = `${targets.length} / ${targets.length}`;
  M.fill.style.width = "100%";
  if (M.note) {
    M.note.textContent = `✅ 완료 — 성공 ${ok} / 실패 ${fail}`;
    M.note.classList.add(fail ? "bulk-bg-fail" : "bulk-bg-done");
  }
  status.textContent = `완료 · 성공 ${ok} / 실패 ${fail}`;
  toast(`일괄 적용 완료 — 성공 ${ok} / 실패 ${fail}`, fail ? "err" : "ok");
  state.slaveDiffCache = {}; state.repoCfgCache = {}; state.slaveCache = {};
  if (state.matrix) renderMatrix();
}

// Buttons to open each server's Nexus admin page for this repository.
function repoOpenPanel() {
  const repo = state.repoDiffName;
  const cols = (state.repoDiff && state.repoDiff.columns) || [];
  const btns = [];
  cols.forEach((col) => {
    const url = adminRepoUrl(col.id, repo);
    if (!url) return;
    btns.push(el("button", {
      type: "button",
      title: `${col.name} Nexus admin에서 '${repo}' 설정 열기`,
      onclick: () => window.open(url, "_blank", "noopener,noreferrer"),
    }, `${col.name} ↗`));
  });
  if (!btns.length) return null;
  return el("div", { class: "settings-card", style: "margin-top:14px" }, [
    el("h3", {}, "저장소 페이지 열기 (admin)"),
    el("p", { class: "hint" }, "각 서버의 Nexus admin에서 이 저장소 설정 화면을 새 탭으로 엽니다."),
    el("div", { class: "form-actions", style: "justify-content:flex-start;flex-wrap:wrap;gap:8px" }, btns),
  ]);
}

// Offer to align each slave (proxy → managed master) repo with its master,
// keeping the slave's own remoteUrl.
function repoSlaveSyncPanel() {
  const repo = state.repoDiffName;
  const cols = (state.repoDiff && state.repoDiff.columns) || [];
  const fields = (state.repoDiff && state.repoDiff.fields) || [];
  const fmap = {};
  fields.forEach((f) => { fmap[f.key] = f.values; });
  const colIds = new Set(cols.map((c) => c.id));
  const skip = new Set(["proxy.remoteUrl", "url", "name"]);
  const rows = [];
  cols.forEach((col) => {
    const remote = fmap["proxy.remoteUrl"] ? fmap["proxy.remoteUrl"][col.id] : null;
    if (!remote) return;
    const h = hostOf(remote);
    const master = (state.instances || []).find((i) => i.id !== col.id && instHosts(i).includes(h));
    if (!master) return;
    let diffN = null;
    if (colIds.has(master.id)) {
      diffN = 0;
      fields.forEach((f) => {
        if (skip.has(f.key)) return;
        if (f.values[col.id] !== f.values[master.id]) diffN++;
      });
      if (diffN === 0) return;  // already matching — nothing to do
    }
    const label = diffN == null ? "마스터에 맞추기" : `${diffN}개 항목 다름 — 마스터에 맞추기`;
    rows.push(el("div", { class: "form-actions", style: "justify-content:flex-start;gap:10px" }, [
      el("span", {}, `${col.name} → ${master.name} Slave`),
      el("button", {
        type: "button",
        onclick: () => syncSlaveConfig(repo, col.id, master.id, col.name, master.name),
      }, label),
    ]));
  });
  if (!rows.length) return null;
  return el("div", { class: "settings-card", style: "margin-top:14px" }, [
    el("h3", {}, "슬레이브 설정 맞추기 (proxy URL 유지)"),
    el("p", { class: "hint" },
      "프록시 remoteUrl(마스터를 가리킴)은 그대로 두고, 나머지 설정을 마스터와 동일하게 맞춥니다."),
    ...rows,
  ]);
}

async function syncSlaveConfig(repo, slaveId, masterId, sName, mName) {
  if (!confirm(
    `'${sName}'의 '${repo}' 설정을 '${mName}'에 맞춥니다.\n` +
    `프록시 remoteUrl(→ 마스터)만 유지하고, 나머지 설정을 마스터와 동일하게 덮어씁니다.\n\n진행할까요?`
  )) return;
  try {
    await api(
      `/api/matrix/sync-slave-config?repository=${encodeURIComponent(repo)}` +
        `&slave_id=${encodeURIComponent(slaveId)}&master_id=${encodeURIComponent(masterId)}`,
      { method: "POST" }
    );
    toast(`'${sName}' 설정을 '${mName}'에 맞췄습니다 (remoteUrl 유지)`);
    state.slaveDiffCache = {};
    state.repoCfgCache = {};
    state.slaveCache = {};
    if (state.matrix) renderMatrix();
    openRepoDiff(repo);  // refresh the popup
  } catch (e) {
    toast(`맞추기 실패: ${e.message}`, "err");
  }
}

// Panel to warm a target proxy's cache for this repo using a source's assets.
function repoCacheSyncPanel() {
  const repo = state.repoDiffName;
  const cols = (state.repoDiff && state.repoDiff.columns) || [];
  const src = el("select", { id: "warm-src" }, cols.map((c) => el("option", { value: c.id }, c.name)));
  const tgt = el("select", { id: "warm-tgt" }, cols.map((c) => el("option", { value: c.id }, c.name)));
  if (cols.length > 1) tgt.selectedIndex = 1;
  const status = el("span", { class: "hint", style: "margin:0" });
  const btn = el("button", {
    type: "button",
    onclick: () => warmRepoCache(repo, src.value, tgt.value, src, tgt, status),
  }, "캐시 동기화 시작");
  return el("div", { class: "settings-card", style: "margin-top:14px" }, [
    el("h3", {}, "프록시 캐시 동기화 (데이터)"),
    el("p", { class: "hint" },
      `원본 서버의 '${repo}' 캐시 자산 목록을 받아, 대상 서버에서 각 파일을 당겨 캐시를 채웁니다. ` +
      `대상은 프록시 저장소여야 하며(자기 업스트림에서 받아옴), 용량이 크면 시간이 걸립니다.`),
    el("div", { class: "form-actions", style: "justify-content:flex-start;flex-wrap:wrap;gap:8px" }, [
      el("label", { class: "ref-pick" }, ["원본 ", src]),
      el("label", { class: "ref-pick" }, ["대상 ", tgt]),
      btn, status,
    ]),
  ]);
}

async function warmRepoCache(repo, sourceId, targetId, srcSel, tgtSel, status) {
  if (!sourceId || !targetId) { toast("원본/대상 서버를 선택하세요.", "err"); return; }
  if (sourceId === targetId) { toast("원본과 대상이 같습니다.", "err"); return; }
  const sName = srcSel.options[srcSel.selectedIndex].text;
  const tName = tgtSel.options[tgtSel.selectedIndex].text;
  if (!confirm(
    `'${sName}'의 '${repo}' 캐시 자산 목록을 받아 '${tName}'에서 각 파일을 당겨 캐시를 채웁니다.\n` +
    `(대상은 프록시여야 함. 대용량이면 오래 걸립니다.)\n\n진행할까요?`
  )) return;
  let token = "";
  let warmed = 0, failed = 0, processed = 0, done = false, guard = 0;
  const t0 = Date.now();
  try {
    while (!done && guard < 100000) {
      guard++;
      const r = await api(
        `/api/instances/${encodeURIComponent(targetId)}/cache-warm` +
          `?source_id=${encodeURIComponent(sourceId)}&repository=${encodeURIComponent(repo)}` +
          `&token=${encodeURIComponent(token)}&pages=5`,
        { method: "POST" }
      );
      warmed += r.warmed; failed += r.failed; processed += r.processed;
      const sec = Math.round((Date.now() - t0) / 1000);
      status.textContent = `진행 중… 처리 ${processed} · 캐시 ${warmed} · 실패 ${failed} (${sec}초)`;
      token = r.next_token || "";
      done = r.done;
      if (!done && !token) break;
    }
    status.textContent = `완료 · 처리 ${processed} · 캐시 ${warmed} · 실패 ${failed}`;
    toast(`캐시 동기화 완료 — ${tName}: ${warmed}개 캐시 / ${failed} 실패`, failed ? "err" : "ok");
  } catch (e) {
    status.textContent = `중단: ${e.message} (처리 ${processed} · 캐시 ${warmed})`;
    toast(`캐시 동기화 실패: ${e.message}`, "err");
  }
}

async function openRepoDiff(name) {
  document.getElementById("repo-modal-title").textContent = `저장소 설정 비교 — ${name}`;
  state.repoDiffName = name;
  const modal = document.getElementById("repo-modal");
  const body = document.getElementById("repo-modal-body");
  modal.classList.remove("hidden");
  body.innerHTML = "";
  body.append(el("div", { class: "empty" }, "불러오는 중…"));
  try {
    state.repoDiff = await api(`/api/repository-detail?repository=${encodeURIComponent(name)}`);
  } catch (e) {
    body.innerHTML = "";
    body.append(el("div", { class: "empty" }, `비교 정보를 불러오지 못했습니다: ${e.message}`));
    return;
  }
  renderRepoDiff();
}

function closeRepoDiff() {
  document.getElementById("repo-modal").classList.add("hidden");
  state.repoDiff = null;
}

document.getElementById("repo-modal-close").addEventListener("click", closeRepoDiff);
document.getElementById("repo-diff-only").addEventListener("change", renderRepoDiff);
document.getElementById("repo-modal").addEventListener("click", (ev) => {
  if (ev.target.id === "repo-modal") closeRepoDiff();
});

// ---- repository 1:1 compare ----------------------------------------------

function fillInstanceSelect(sel) {
  sel.innerHTML = "";
  state.instances.forEach((i) => sel.append(el("option", { value: i.id }, i.name)));
}

// Case-insensitive name comparator for sorting repository/instance lists.
function byName(a, b) {
  const x = (a.name || "").toLowerCase();
  const y = (b.name || "").toLowerCase();
  return x < y ? -1 : x > y ? 1 : 0;
}

async function fillRepoSelect(instanceId, repoSel) {
  repoSel.innerHTML = "";
  repoSel.append(el("option", { value: "" }, "불러오는 중…"));
  try {
    const repos = await api(`/api/instances/${instanceId}/repositories`);
    repoSel.innerHTML = "";
    if (!repos.length) {
      repoSel.append(el("option", { value: "" }, "저장소 없음"));
      return;
    }
    repos.sort(byName).forEach((r) =>
      repoSel.append(el("option", { value: r.name }, `${r.name} (${r.format || "?"}/${r.type || "?"})`))
    );
  } catch (e) {
    repoSel.innerHTML = "";
    repoSel.append(el("option", { value: "" }, "조회 실패"));
  }
}

function setupCompare() {
  const li = document.getElementById("cmp-left-inst");
  const ri = document.getElementById("cmp-right-inst");
  const lr = document.getElementById("cmp-left-repo");
  const rr = document.getElementById("cmp-right-repo");
  fillInstanceSelect(li);
  fillInstanceSelect(ri);
  // Default the right side to a different server when possible.
  if (state.instances.length > 1) ri.value = state.instances[1].id;
  li.addEventListener("change", () => fillRepoSelect(li.value, lr));
  ri.addEventListener("change", () => fillRepoSelect(ri.value, rr));
  if (li.value) fillRepoSelect(li.value, lr);
  if (ri.value) fillRepoSelect(ri.value, rr);
}

function renderCompare() {
  const c = document.getElementById("cmp-result");
  c.innerHTML = "";
  if (!state.compareDiff) return;
  c.append(diffTable(state.compareDiff, document.getElementById("cmp-diff-only").checked));
}

async function runCompare() {
  const li = document.getElementById("cmp-left-inst").value;
  const lr = document.getElementById("cmp-left-repo").value;
  const ri = document.getElementById("cmp-right-inst").value;
  const rr = document.getElementById("cmp-right-repo").value;
  if (!li || !lr || !ri || !rr) {
    toast("양쪽 서버와 저장소를 모두 선택하세요.", "err");
    return;
  }
  const c = document.getElementById("cmp-result");
  c.innerHTML = "";
  c.append(el("div", { class: "empty" }, "비교 중…"));
  const url =
    `/api/compare?left_instance=${encodeURIComponent(li)}&left_repo=${encodeURIComponent(lr)}` +
    `&right_instance=${encodeURIComponent(ri)}&right_repo=${encodeURIComponent(rr)}`;
  try {
    state.compareDiff = await api(url);
  } catch (e) {
    c.innerHTML = "";
    c.append(el("div", { class: "empty" }, `비교 실패: ${e.message}`));
    return;
  }
  renderCompare();
}

document.getElementById("cmp-run").addEventListener("click", runCompare);
document.getElementById("cmp-diff-only").addEventListener("change", renderCompare);

// ---- repositories --------------------------------------------------------

function buildTable(headers, rows) {
  const thead = el("thead", {}, el("tr", {}, headers.map((h) => el("th", {}, h))));
  const tbody = el("tbody", {}, rows);
  return el("table", {}, [thead, tbody]);
}

function repoInst() {
  return document.getElementById("repo-inst").value;
}

function setupRepositories() {
  const sel = document.getElementById("repo-inst");
  fillInstanceSelect(sel);
  sel.addEventListener("change", loadRepositories);
  document.getElementById("repo-refresh").addEventListener("click", loadRepositories);
  loadRepositories();
}

async function loadRepositories() {
  const container = document.getElementById("repo-table");
  container.innerHTML = "";
  document.getElementById("component-heading").classList.add("hidden");
  document.getElementById("component-table").innerHTML = "";
  document.getElementById("component-pager").classList.add("hidden");
  const inst = repoInst();
  if (!inst) return;

  let repos = [];
  try {
    repos = await api(`/api/instances/${inst}/repositories`);
  } catch (e) {
    container.append(el("div", { class: "empty" }, `저장소 조회 실패: ${e.message}`));
    return;
  }
  if (!repos.length) {
    container.append(el("div", { class: "empty" }, "저장소가 없습니다."));
    return;
  }
  repos.sort(byName);
  const rows = repos.map((r) =>
    el("tr", {}, [
      el("td", {}, el("span", { class: "link", onclick: () => browseComponents(r.name) }, r.name)),
      el("td", {}, r.format || "—"),
      el("td", {}, r.type || "—"),
      el("td", {}, r.online === false ? el("span", { class: "badge down" }, "offline") : el("span", { class: "badge up" }, "online")),
      el("td", {}, [
        el("button", { onclick: () => openRepoDiff(r.name) }, "비교"),
        " ",
        el("button", { class: "danger", onclick: () => deleteRepo(r.name) }, "삭제"),
      ]),
    ])
  );
  container.append(buildTable(["이름", "포맷", "유형", "상태", ""], rows));
}

async function deleteRepo(name) {
  if (!confirm(`저장소 '${name}'를 삭제하시겠습니까? 되돌릴 수 없습니다.`)) return;
  try {
    await api(`/api/instances/${repoInst()}/repositories/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    toast(`저장소 '${name}' 삭제됨`);
    loadRepositories();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function browseComponents(repo, append = false) {
  state.componentRepo = repo;
  const heading = document.getElementById("component-heading");
  const table = document.getElementById("component-table");
  const pager = document.getElementById("component-pager");
  heading.textContent = `컴포넌트 — ${repo}`;
  heading.classList.remove("hidden");

  let url = `/api/instances/${repoInst()}/components?repository=${encodeURIComponent(repo)}`;
  if (append && state.componentToken) url += `&continuation_token=${encodeURIComponent(state.componentToken)}`;

  let page;
  try {
    page = await api(url);
  } catch (e) {
    table.innerHTML = "";
    table.append(el("div", { class: "empty" }, `컴포넌트 조회 실패: ${e.message}`));
    pager.classList.add("hidden");
    return;
  }

  const rows = page.items.map((c) =>
    el("tr", {}, [
      el("td", {}, c.group || "—"),
      el("td", {}, c.name || "—"),
      el("td", {}, c.version || "—"),
      el("td", {}, c.format || "—"),
      el("td", {}, el("button", { class: "danger", onclick: () => deleteComponent(c.id) }, "삭제")),
    ])
  );

  if (!append) table.innerHTML = "";
  if (!append && !rows.length) {
    table.append(el("div", { class: "empty" }, "컴포넌트가 없습니다."));
  } else {
    let tbl = table.querySelector("table");
    if (!tbl) {
      tbl = buildTable(["그룹", "이름", "버전", "포맷", ""], rows);
      table.append(tbl);
    } else {
      rows.forEach((r) => tbl.querySelector("tbody").append(r));
    }
  }

  state.componentToken = page.continuation_token;
  pager.classList.toggle("hidden", !page.continuation_token);
}

async function deleteComponent(id) {
  if (!confirm("이 컴포넌트를 삭제하시겠습니까?")) return;
  try {
    await api(`/api/instances/${repoInst()}/components/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    toast("컴포넌트 삭제됨");
    browseComponents(state.componentRepo);
  } catch (e) {
    toast(e.message, "err");
  }
}

document.getElementById("component-more").addEventListener("click", () => {
  browseComponents(state.componentRepo, true);
});

// ---- download usage ------------------------------------------------------

// Fill the repo dropdown for the downloads tab, with an "all repos" option.
async function fillDownloadRepoSelect(instanceId, repoSel) {
  repoSel.innerHTML = "";
  repoSel.append(el("option", { value: "" }, "— 전체 (모든 저장소) —"));
  try {
    const repos = await api(`/api/instances/${instanceId}/repositories`);
    repos.sort(byName).forEach((r) =>
      repoSel.append(el("option", { value: r.name }, `${r.name} (${r.format || "?"}/${r.type || "?"})`))
    );
  } catch (e) {
    /* repo list failure is non-fatal; the "전체" view will still try. */
  }
}

function clearDownloads() {
  document.getElementById("dl-summary").innerHTML = "";
  document.getElementById("dl-note").textContent = "";
  document.getElementById("dl-table").innerHTML = "";
}

async function setupDownloads() {
  const inst = document.getElementById("dl-inst");
  const repo = document.getElementById("dl-repo");
  fillInstanceSelect(inst);
  inst.addEventListener("change", async () => {
    clearDownloads();                       // selection no longer auto-runs
    await fillDownloadRepoSelect(inst.value, repo);
  });
  repo.addEventListener("change", clearDownloads);
  document.getElementById("dl-hide-errors").addEventListener("change", () => {
    // Re-filter the cached summary without re-scanning.
    if (state.downloadSummary && !repo.value) renderServerSummary();
  });
  if (inst.value) await fillDownloadRepoSelect(inst.value, repo);
}

function summaryCard(label, value) {
  return el("div", { class: "card" }, [
    el("div", { class: "metric" }, [
      el("div", { class: "label" }, label),
      el("div", { class: "value" }, value),
    ]),
  ]);
}

// Dispatch: no repository chosen -> whole-server summary; otherwise detail.
function runDownloadsView() {
  const instId = document.getElementById("dl-inst").value;
  const repo = document.getElementById("dl-repo").value;
  state.dlRunId = (state.dlRunId || 0) + 1;  // invalidates any in-flight load
  if (!instId) return;
  if (repo) {
    loadRepoDownloadDetail(instId, repo);
  } else {
    loadServerDownloadSummary(instId);
  }
}

async function loadServerDownloadSummary(instId) {
  const token = state.dlRunId;
  const table = document.getElementById("dl-table");
  document.getElementById("dl-summary").innerHTML = "";
  document.getElementById("dl-note").textContent = "";
  table.innerHTML = "";
  table.append(el("div", { class: "empty" }, "저장소 목록을 불러오는 중…"));

  // 1) Get the full repository list up front and show every row immediately.
  let repos;
  try {
    repos = await api(`/api/instances/${instId}/repositories`);
  } catch (e) {
    if (state.dlRunId !== token) return;
    table.innerHTML = "";
    table.append(el("div", { class: "empty" }, `조회 실패: ${e.message}`));
    return;
  }
  if (state.dlRunId !== token) return;

  // Group repos aggregate member assets -> excluded; sort case-insensitive.
  repos = repos
    .filter((r) => (r.type || "").toLowerCase() !== "group")
    .sort((a, b) => (a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1));

  state.downloadSummary = {
    instance_id: instId,
    repositories: repos.map((r) => ({
      repository: r.name, format: r.format, type: r.type, pending: true,
    })),
  };
  renderServerSummary();

  // 2) Scan 5 at a time, updating those rows as each batch finishes.
  const byName = {};
  state.downloadSummary.repositories.forEach((r) => (byName[r.repository] = r));
  const names = repos.map((r) => r.name);
  const CHUNK = 5;
  for (let i = 0; i < names.length; i += CHUNK) {
    if (state.dlRunId !== token) return;  // a newer load/started; stop quietly
    const chunk = names.slice(i, i + CHUNK);
    const qs = chunk.map((n) => `repository=${encodeURIComponent(n)}`).join("&");
    let results;
    try {
      results = await api(`/api/instances/${instId}/downloads-batch?${qs}`);
    } catch (e) {
      results = chunk.map((n) => ({ repository: n, error: e.message }));
    }
    if (state.dlRunId !== token) return;
    results.forEach((res) => {
      const row = byName[res.repository];
      if (!row) return;
      row.pending = false;
      // Merge only the scanned metrics; keep format/type from the repo list
      // (the batch result doesn't carry them and would blank them out).
      row.error = res.error || null;
      row.total_assets = res.total_assets;
      row.downloaded_assets = res.downloaded_assets;
      row.total_size_bytes = res.total_size_bytes;
      row.downloaded_size_bytes = res.downloaded_size_bytes;
      row.truncated = res.truncated;
    });
    renderServerSummary();
  }
}

// Sort state for the summary table.
state.dlSort = { col: "repository", dir: "asc" };

const DL_COLUMNS = [
  { key: "repository", label: "저장소", num: false },
  { key: "fmt", label: "포맷/유형", num: false },
  { key: "total_assets", label: "전체 자산", num: true },
  { key: "downloaded_assets", label: "다운로드 자산", num: true },
  { key: "total_size_bytes", label: "전체 용량", num: true },
  { key: "downloaded_size_bytes", label: "다운로드 용량", num: true },
];

function renderServerSummary() {
  const summary = document.getElementById("dl-summary");
  const note = document.getElementById("dl-note");
  const table = document.getElementById("dl-table");
  const data = state.downloadSummary;
  summary.innerHTML = "";
  note.textContent = "";
  table.innerHTML = "";
  if (!data) return;

  const reps = data.repositories;
  const hideErrors = document.getElementById("dl-hide-errors").checked;
  const errorCount = reps.filter((r) => r.error).length;
  const pendingCount = reps.filter((r) => r.pending).length;

  // Running totals from completed, non-error rows.
  const totals = reps.reduce((acc, r) => {
    if (!r.pending && !r.error) {
      acc.ta += r.total_assets || 0;
      acc.ts += r.total_size_bytes || 0;
      acc.ds += r.downloaded_size_bytes || 0;
    }
    return acc;
  }, { ta: 0, ts: 0, ds: 0 });

  summary.append(
    summaryCard("저장소 수", reps.length.toLocaleString()),
    summaryCard("전체 자산", totals.ta.toLocaleString()),
    summaryCard("전체 용량", fmtBytes(totals.ts)),
    summaryCard("다운로드된 용량", fmtBytes(totals.ds))
  );

  let rows = reps.slice();
  if (hideErrors) rows = rows.filter((r) => !r.error);

  // Sort: pending rows stay in place by name; error rows sink to the bottom.
  const { col, dir } = state.dlSort;
  const colDef = DL_COLUMNS.find((c) => c.key === col) || DL_COLUMNS[0];
  const val = (r) => {
    if (col === "fmt") return `${r.format || ""}/${r.type || ""}`.toLowerCase();
    if (colDef.num) return r[col] || 0;
    return (r[col] || "").toLowerCase();
  };
  rows.sort((a, b) => {
    if (!!a.error !== !!b.error) return a.error ? 1 : -1;
    let cmp;
    if (colDef.num) cmp = val(a) - val(b);
    else cmp = val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  });

  if (!rows.length) {
    table.append(el("div", { class: "empty" },
      hideErrors && errorCount ? "표시할 (조회 가능한) 저장소가 없습니다." : "스캔할 저장소가 없습니다."));
    return;
  }

  const headCells = DL_COLUMNS.map((c) => {
    const arrow = state.dlSort.col === c.key ? (state.dlSort.dir === "asc" ? " ▲" : " ▼") : "";
    return el("th", {
      class: "sortable",
      onclick: () => {
        if (state.dlSort.col === c.key) state.dlSort.dir = state.dlSort.dir === "asc" ? "desc" : "asc";
        else { state.dlSort.col = c.key; state.dlSort.dir = c.num ? "desc" : "asc"; }
        renderServerSummary();
      },
    }, c.label + arrow);
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const body = rows.map((r) => {
    const name = el("span", { class: "link", title: "상세 보기", onclick: () => openRepoDownloadDetail(r.repository) }, r.repository);
    const fmt = el("td", {}, `${r.format || "?"}/${r.type || "?"}`);
    if (r.pending) {
      return el("tr", { class: "dl-pending" }, [
        el("td", {}, name), fmt,
        el("td", { colspan: "4", class: "num pending" }, "조회 중…"),
      ]);
    }
    if (r.error) {
      return el("tr", {}, [
        el("td", {}, name), fmt,
        el("td", { colspan: "4", class: "site-error" }, `조회 불가: ${r.error}`),
      ]);
    }
    return el("tr", {}, [
      el("td", {}, name), fmt,
      el("td", { class: "num" }, (r.total_assets || 0).toLocaleString()),
      el("td", { class: "num" }, (r.downloaded_assets || 0).toLocaleString()),
      el("td", { class: "num" }, fmtBytes(r.total_size_bytes)),
      el("td", { class: "num" }, fmtBytes(r.downloaded_size_bytes) + (r.truncated ? " *" : "")),
    ]);
  });
  table.append(el("table", { class: "dl-summary" }, [thead, el("tbody", {}, body)]));

  const notes = [];
  if (pendingCount) notes.push(`진행 ${reps.length - pendingCount}/${reps.length} …`);
  if (errorCount) notes.push(`조회 불가 ${errorCount}개`);
  if (reps.some((r) => r.truncated)) notes.push("'*'는 일부만 스캔(하한값)");
  note.textContent = notes.length ? `※ ${notes.join(" · ")}` : "";
}

// Select a repo in the dropdown and show its detail (used by summary links).
function openRepoDownloadDetail(repoName) {
  document.getElementById("dl-repo").value = repoName;
  runDownloadsView();
}

async function loadRepoDownloadDetail(instId, repo) {
  const summary = document.getElementById("dl-summary");
  const note = document.getElementById("dl-note");
  const table = document.getElementById("dl-table");
  summary.innerHTML = "";
  note.textContent = "";
  table.innerHTML = "";
  table.append(el("div", { class: "empty" }, "자산을 스캔하는 중… (저장소 크기에 따라 시간이 걸릴 수 있어요)"));

  let report;
  try {
    report = await api(
      `/api/instances/${instId}/downloads?repository=${encodeURIComponent(repo)}`
    );
  } catch (e) {
    table.innerHTML = "";
    table.append(el("div", { class: "empty" }, `조회 실패: ${e.message}`));
    return;
  }

  summary.append(
    summaryCard("전체 자산", report.total_assets.toLocaleString()),
    summaryCard("다운로드된 자산", report.downloaded_assets.toLocaleString()),
    summaryCard("전체 용량", fmtBytes(report.total_size_bytes)),
    summaryCard("다운로드된 용량", fmtBytes(report.downloaded_size_bytes))
  );

  if (report.truncated) {
    note.textContent =
      "※ 자산이 매우 많아 일부만 스캔했습니다. 위 수치는 최소값(하한)입니다.";
  }

  table.innerHTML = "";
  if (!report.items.length) {
    table.append(el("div", { class: "empty" }, "다운로드된 자산이 없습니다."));
    return;
  }
  const rows = report.items.map((a) =>
    el("tr", {}, [
      el("td", {}, a.path),
      el("td", {}, a.content_type || "—"),
      el("td", { class: "num" }, fmtBytes(a.size_bytes)),
      el("td", {}, fmtDate(a.last_downloaded)),
    ])
  );
  table.append(buildTable(["경로", "유형", "용량", "마지막 다운로드"], rows));
}

document.getElementById("dl-run").addEventListener("click", runDownloadsView);

// ---- scheduled tasks -----------------------------------------------------

function setupTasks() {
  const inst = document.getElementById("task-inst");
  fillInstanceSelect(inst);
  inst.addEventListener("change", loadTasks);
  document.getElementById("task-refresh").addEventListener("click", loadTasks);
}

function taskResultBadge(result, state) {
  if (state && state !== "WAITING") {
    return el("span", { class: "badge warn" }, state);     // RUNNING 등
  }
  if (!result) return el("span", { class: "badge" }, "—");
  const ok = result === "OK" || result === "SUCCESS";
  return el("span", { class: `badge ${ok ? "up" : "down"}` }, result);
}

async function loadTasks() {
  const instId = document.getElementById("task-inst").value;
  const container = document.getElementById("task-table");
  container.innerHTML = "";
  if (!instId) return;
  container.append(el("div", { class: "empty" }, "불러오는 중…"));
  let list;
  try {
    list = await api(`/api/instances/${instId}/tasks`);
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `작업 조회 실패: ${e.message}`));
    return;
  }
  container.innerHTML = "";
  if (!list.length) {
    container.append(el("div", { class: "empty" }, "등록된 작업이 없습니다."));
    return;
  }
  const rows = list.map((t) => {
    const actions = [];
    if (t.runnable) actions.push(el("button", { onclick: () => taskAction(instId, t.id, "run", t.name) }, "실행"));
    if (t.stoppable) actions.push(el("button", { class: "danger", onclick: () => taskAction(instId, t.id, "stop", t.name) }, "중지"));
    return el("tr", {}, [
      el("td", {}, t.name || t.id),
      el("td", {}, t.type || "—"),
      el("td", {}, taskResultBadge(t.last_run_result, t.current_state)),
      el("td", {}, fmtDate(t.last_run)),
      el("td", {}, fmtDate(t.next_run)),
      el("td", {}, actions.length ? actions : "—"),
    ]);
  });
  container.append(buildTable(["작업", "유형", "마지막 결과", "마지막 실행", "다음 실행", ""], rows));
}

async function taskAction(instId, taskId, action, name) {
  const verb = action === "run" ? "실행" : "중지";
  if (!confirm(`작업 '${name}'을(를) ${verb}하시겠습니까?`)) return;
  try {
    await api(`/api/instances/${instId}/tasks/${encodeURIComponent(taskId)}/${action}`, { method: "POST" });
    toast(`작업 ${verb} 요청됨`);
    setTimeout(loadTasks, 800);
  } catch (e) {
    toast(e.message, "err");
  }
}

// ---- alerts --------------------------------------------------------------

function setupAlerts() {
  document.getElementById("alerts-refresh").addEventListener("click", loadAlerts);
}

async function loadAlerts() {
  const cfg = document.getElementById("alerts-config");
  const container = document.getElementById("alerts-table");
  cfg.textContent = "";
  container.innerHTML = "";
  container.append(el("div", { class: "empty" }, "점검 중…"));
  let data;
  try {
    data = await api("/api/alerts?refresh=true");
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `알림 조회 실패: ${e.message}`));
    return;
  }
  cfg.textContent = data.webhook_configured
    ? `Webhook: 설정됨 · 점검 주기 ${data.interval}초`
    : `Webhook: 미설정 (환경변수 NEXUS_MANAGER_ALERT_WEBHOOK 로 Slack/Webhook URL 지정) · 점검 주기 ${data.interval}초`;

  container.innerHTML = "";
  if (!data.alerts.length) {
    container.append(el("div", { class: "empty" }, "현재 알림 없음 ✓"));
    return;
  }
  const rows = data.alerts.map((a) =>
    el("tr", { class: a.severity === "critical" ? "differs" : "" }, [
      el("td", {}, a.severity === "critical"
        ? el("span", { class: "badge down" }, "심각")
        : el("span", { class: "badge warn" }, "경고")),
      el("td", {}, a.node || "—"),
      el("td", {}, a.message),
    ])
  );
  container.append(buildTable(["심각도", "노드", "내용"], rows));
}

// ---- security check ------------------------------------------------------

function setupSecurity() {
  document.getElementById("security-refresh").addEventListener("click", loadSecurity);
}

function yesNoBadge(value, riskWhenTrue, labels) {
  // value: boolean|null ; labels: [trueLabel, falseLabel]
  if (value === null || value === undefined) return el("span", { class: "badge" }, "—");
  const risky = value === riskWhenTrue;
  return el("span", { class: `badge ${risky ? "down" : "up"}` }, value ? labels[0] : labels[1]);
}

async function loadSecurity() {
  const container = document.getElementById("security-table");
  container.innerHTML = "";
  container.append(el("div", { class: "empty" }, "점검 중…"));
  let list;
  try {
    list = await api("/api/security");
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `보안 점검 실패: ${e.message}`));
    return;
  }
  container.innerHTML = "";
  if (!list.length) {
    container.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다."));
    return;
  }
  // Fleet summary for at-a-glance scanning.
  const summary = document.getElementById("security-summary");
  if (summary) {
    const warn = list.filter((s) => s.risk === "warn").length;
    const anon = list.filter((s) => s.anonymous_enabled).length;
    const unk = list.filter((s) => !s.reachable || s.risk === "unknown").length;
    summary.innerHTML = "";
    summary.append(
      summaryCard("서버", String(list.length)),
      summaryCard("점검 필요", String(warn)),
      summaryCard("익명 접근 허용", String(anon)),
      summaryCard("조회 불가", String(unk)),
    );
  }
  const rows = list.map((s) => {
    if (!s.reachable) {
      return el("tr", {}, [
        el("td", {}, s.name),
        el("td", {}, el("span", { class: "badge warn" }, "조회 불가")),
        el("td", { colspan: "4", class: "site-error" }, s.error || ""),
      ]);
    }
    const adminList = s.admin_users && s.admin_users.length ? s.admin_users.join(", ") : "—";
    const riskBadge = s.risk === "warn"
      ? el("span", { class: "badge down", title: (s.issues || []).join(", ") }, "⚠ 점검")
      : (s.risk === "unknown"
          ? el("span", { class: "badge warn", title: s.error || "" }, "확인불가")
          : el("span", { class: "badge up" }, "양호"));
    return el("tr", {}, [
      el("td", {}, s.name),
      el("td", {}, riskBadge),
      el("td", {}, yesNoBadge(s.anonymous_enabled, true, ["허용", "차단"])),
      el("td", {}, yesNoBadge(s.admin_active, true, ["활성", "비활성"])),
      el("td", { title: adminList }, `${s.admin_users ? s.admin_users.length : "—"}${adminList !== "—" ? " (" + adminList + ")" : ""}`),
      el("td", { class: "num" }, s.user_count != null ? s.user_count.toLocaleString() : "—"),
    ]);
  });
  container.append(buildTable(
    ["서버", "상태", "익명 접근", "기본 admin 계정", "관리자 권한 계정", "사용자 수"], rows
  ));
}

// ---- content sync compare ------------------------------------------------

async function setupContent() {
  const sel = document.getElementById("content-repo");
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "저장소 목록 불러오는 중…"));
  // Repository names = union across instances, taken from the matrix.
  try {
    const matrix = state.matrix || (await api("/api/matrix"));
    state.matrix = matrix;
    sel.innerHTML = "";
    const names = matrix.rows.map((r) => r.repository);
    if (!names.length) sel.append(el("option", { value: "" }, "저장소 없음"));
    names.forEach((n) => sel.append(el("option", { value: n }, n)));
  } catch (e) {
    sel.innerHTML = "";
    sel.append(el("option", { value: "" }, "목록 조회 실패"));
  }
  document.getElementById("content-run").addEventListener("click", loadContent);
  document.getElementById("content-diff-only").addEventListener("change", renderContent);
}

function renderContent() {
  const container = document.getElementById("content-table");
  const note = document.getElementById("content-note");
  container.innerHTML = "";
  const data = state.contentMatrix;
  if (!data) return;

  note.textContent = data.truncated
    ? "※ 컴포넌트가 매우 많아 일부만 스캔했습니다(하한). 결과가 불완전할 수 있어요."
    : "";

  const applicable = data.columns.filter((c) => c.reachable && !c.error);
  const diffOnly = document.getElementById("content-diff-only").checked;
  let rows = data.rows;
  if (diffOnly) rows = rows.filter((r) => !r.consistent);

  if (!data.columns.length) {
    container.append(el("div", { class: "empty" }, "인스턴스가 없습니다."));
    return;
  }
  if (!rows.length) {
    container.append(el("div", { class: "empty" },
      diffOnly ? "사이트 간 차이가 없습니다. 모두 동일합니다 ✓" : "컴포넌트가 없습니다."));
    return;
  }

  const headCells = [el("th", { class: "rowhead" }, "컴포넌트 \\ 사이트")];
  data.columns.forEach((col) => {
    let label = col.name;
    if (!col.reachable) label += " ⚠";
    else if (col.error) label += " (없음)";
    headCells.push(el("th", { title: col.error || col.name }, label));
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const body = rows.map((r) => {
    const tds = [el("td", { class: "rowhead" }, r.key)];
    data.columns.forEach((col) => {
      const applies = col.reachable && !col.error;
      let cls, mark;
      if (!applies) { cls = "unknown"; mark = "·"; }
      else if (r.present[col.id]) { cls = "consistent"; mark = "✓"; }
      else { cls = "drift"; mark = "✗"; }
      tds.push(el("td", {}, el("span", { class: `mcell ${cls}` }, el("span", { class: "mark" }, mark))));
    });
    return el("tr", {}, tds);
  });

  container.append(el("table", { class: "matrix" }, [thead, el("tbody", {}, body)]));
}

async function loadContent() {
  const repo = document.getElementById("content-repo").value;
  const container = document.getElementById("content-table");
  document.getElementById("content-note").textContent = "";
  container.innerHTML = "";
  if (!repo) { toast("저장소를 선택하세요.", "err"); return; }
  container.append(el("div", { class: "empty" }, "사이트별 컴포넌트를 스캔하는 중…"));
  try {
    state.contentMatrix = await api(`/api/content-compare?repository=${encodeURIComponent(repo)}`);
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `비교 실패: ${e.message}`));
    return;
  }
  renderContent();
}

// ---- server settings (instance management) -------------------------------

const SETTINGS_SELECTORS = ["cmp-left-inst", "cmp-right-inst", "dl-inst", "task-inst", "repo-inst", "cleanup-inst"];

async function refreshInstances() {
  state.instances = await api("/api/instances");
  // Refill the standalone instance dropdowns, keeping selection if possible.
  SETTINGS_SELECTORS.forEach((id) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const prev = sel.value;
    fillInstanceSelect(sel);
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  });
  // Invalidate cached comparison data so it rebuilds with the new set.
  state.matrix = null;
  state.contentSetup = false;
}

function showSettingsForm(show) {
  document.getElementById("settings-form-box").classList.toggle("hidden", !show);
}

function settingsResetForm() {
  const form = document.getElementById("settings-form");
  form.reset();
  form.editing_id.value = "";
  form.id.disabled = false;
  form.use_in_monitoring.checked = true;
  form.use_in_comparison.checked = true;
  document.getElementById("settings-form-title").textContent = "새 서버 추가";
  document.getElementById("settings-submit").textContent = "서버 추가";
}

function settingsEdit(inst) {
  const form = document.getElementById("settings-form");
  showSettingsForm(true);
  form.editing_id.value = inst.id;
  form.id.value = inst.id;
  form.id.disabled = true;                 // id is the key; not editable
  form.name.value = inst.name;
  form.group.value = inst.group || "";
  form.tier.value = inst.tier || 0;
  form.timezone.value = inst.timezone || "";
  form.base_url.value = inst.base_url;
  form.alt_url.value = inst.alt_url || "";
  form.username.value = inst.username || "";
  form.password.value = "";                // blank = keep existing
  form.verify_tls.checked = inst.verify_tls === true;
  form.use_in_monitoring.checked = inst.use_in_monitoring !== false;
  form.use_in_comparison.checked = inst.use_in_comparison !== false;
  document.getElementById("settings-form-title").textContent = `서버 수정 — ${inst.name}`;
  document.getElementById("settings-submit").textContent = "변경 저장";
  document.getElementById("settings-form-box").scrollIntoView({ behavior: "smooth" });
}

function flagToggle(inst, field) {
  const on = inst[field] !== false;
  return el("span", {
    class: `badge ${on ? "up" : "down"} flag-toggle`,
    title: "클릭하여 전환",
    onclick: () => toggleFlag(inst, field),
  }, on ? "✓ 사용" : "✗ 제외");
}

async function toggleFlag(inst, field) {
  const body = {
    name: inst.name,
    group: inst.group || "",
    tier: inst.tier || 0,
    timezone: inst.timezone || "",
    base_url: inst.base_url,
    alt_url: inst.alt_url || "",
    username: inst.username || "",
    password: "",                       // blank keeps the stored password
    verify_tls: inst.verify_tls,
    use_in_monitoring: inst.use_in_monitoring !== false,
    use_in_comparison: inst.use_in_comparison !== false,
  };
  body[field] = !(inst[field] !== false);  // flip
  try {
    await api(`/api/instances/${encodeURIComponent(inst.id)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    await refreshInstances();
    loadSettings();
  } catch (e) {
    toast(e.message, "err");
  }
}

// Server-list columns; those with `sk` are sortable by clicking the header.
const SETTINGS_COLS = [
  { label: "이름", sk: (i) => i.name },
  { label: "식별자", sk: (i) => i.id },
  { label: "그룹", sk: (i) => i.group || "" },
  { label: "주소", sk: (i) => i.base_url || "" },
  { label: "계정", sk: (i) => i.username || "" },
  { label: "모니터링" }, { label: "비교" }, { label: "기준" }, { label: "" },
];

function renderSettingsTable(list) {
  const container = document.getElementById("settings-table");
  container.innerHTML = "";
  const sort = state.settingsSort;
  let data = list.slice();
  if (sort && sort.col) {
    const col = SETTINGS_COLS.find((c) => c.label === sort.col);
    if (col && col.sk) {
      data.sort((a, b) => {
        const va = String(col.sk(a) ?? "").toLowerCase();
        const vb = String(col.sk(b) ?? "").toLowerCase();
        return (va < vb ? -1 : va > vb ? 1 : 0) * (sort.dir === "desc" ? -1 : 1);
      });
    }
  }
  const ths = SETTINGS_COLS.map((c) => {
    if (!c.sk) return el("th", {}, c.label);
    const active = sort && sort.col === c.label;
    return el("th", {
      class: `sortable${active ? " sorted" : ""}`,
      title: "클릭하여 정렬",
      onclick: () => {
        if (sort && sort.col === c.label) sort.dir = sort.dir === "asc" ? "desc" : "asc";
        else state.settingsSort = { col: c.label, dir: "asc" };
        renderSettingsTable(state.instances || []);
      },
    }, c.label + (active ? (sort.dir === "desc" ? " ▼" : " ▲") : " ⇅"));
  });
  const rows = data.map((i) =>
    el("tr", {}, [
      el("td", {}, i.name),
      el("td", {}, i.id),
      el("td", {}, (i.group || "—") + (i.tier ? ` · 계위${i.tier}` : "")),
      el("td", {}, i.alt_url ? `${i.base_url} (별칭: ${i.alt_url})` : i.base_url),
      el("td", {}, i.username || "—"),
      el("td", {}, flagToggle(i, "use_in_monitoring")),
      el("td", {}, flagToggle(i, "use_in_comparison")),
      el("td", {}, el("span", {
        class: `ref-star ${i.is_reference ? "on" : ""}`,
        title: i.is_reference ? "기준 서버 (클릭하여 해제)" : "이 서버를 비교 기준으로 지정",
        onclick: () => setReference(i),
      }, i.is_reference ? "★ 기준" : "☆")),
      el("td", {}, [
        el("button", { onclick: () => settingsEdit(i) }, "수정"),
        " ",
        el("button", {
          title: "이 서버의 현재 Nexus 설정(저장소·blob·보안·작업 등)을 JSON으로 다운로드",
          onclick: () => downloadInstanceConfig(i),
        }, "설정 ↓"),
        " ",
        el("button", {
          title: "다운로드한 구성 JSON을 이 서버에 복구(저장소·blob·정책 등 재생성, 기존 항목은 건너뜀)",
          onclick: () => restoreInstanceConfig(i),
        }, "복구 ↑"),
        " ",
        el("button", { class: "danger", onclick: () => settingsDelete(i) }, "삭제"),
      ]),
    ])
  );
  container.append(el("table", {}, [
    el("thead", {}, el("tr", {}, ths)),
    el("tbody", {}, rows),
  ]));
}

async function loadSettings() {
  const container = document.getElementById("settings-table");
  container.innerHTML = "";
  let list = state.instances;
  try {
    list = await api("/api/instances");
    state.instances = list;
  } catch (e) {
    container.append(el("div", { class: "empty" }, `목록 조회 실패: ${e.message}`));
    return;
  }
  if (!list.length) {
    container.append(el("div", { class: "empty" }, "등록된 서버가 없습니다. 아래에서 추가하세요."));
    return;
  }
  renderSettingsTable(list);
  loadGroupOrder();
  loadCompareFields();
  loadPingConfig();
  loadBackupConfig();
  loadSyncJobs();
}

function downloadInstanceConfig(inst) {
  // Collecting the full config (one call per repository) can take a moment.
  toast(`${inst.name} 설정 수집 중… 잠시 후 다운로드가 시작됩니다.`);
  window.location.href = `/api/instances/${encodeURIComponent(inst.id)}/config-export`;
}

let restoreTargetInst = null;

function restoreInstanceConfig(inst) {
  restoreTargetInst = inst;
  const fi = document.getElementById("restore-file");
  fi.value = "";
  fi.click();
}

async function applyRestoreFile(file) {
  const inst = restoreTargetInst;
  if (!inst) return;
  let snapshot;
  try {
    snapshot = JSON.parse(await file.text());
  } catch (e) {
    toast(`JSON 파싱 실패: ${e.message}`, "err");
    return;
  }
  const includeSec = document.getElementById("restore-include-security")?.checked;
  const mode = document.getElementById("restore-mode")?.value || "merge";
  const base = ["blobStores", "cleanupPolicies", "routingRules", "repositories"];
  const sec = ["contentSelectors", "privileges", "roles", "users", "anonymous"];
  const sections = includeSec ? base.concat(sec) : base;
  const srcName = (snapshot.instance && snapshot.instance.name) || "(알 수 없음)";
  const repoCount = ((snapshot.sections || {}).repositories || []).length;
  const modeLabel = mode === "overwrite" ? "덮어쓰기 — 기존 항목도 갱신됩니다" : "병합 — 기존 항목은 그대로 둡니다";
  if (
    !confirm(
      `'${inst.name}' 서버에 구성을 가져옵니다(import).\n` +
        `원본 스냅샷: ${srcName} (저장소 ${repoCount}개)\n` +
        `방식: ${modeLabel}\n` +
        `대상: ${sections.join(", ")}\n` +
        (includeSec ? "보안 포함 — 신규 사용자는 임시 비밀번호로 생성됩니다.\n" : "") +
        `\n진행할까요?`
    )
  )
    return;
  const box = document.getElementById("restore-result");
  box.innerHTML = "";
  toast(`${inst.name} 구성 가져오는 중… (${mode})`);
  try {
    const r = await api(
      `/api/instances/${encodeURIComponent(inst.id)}/config-restore?mode=${mode}&sections=${sections.join(",")}`,
      { method: "POST", body: JSON.stringify(snapshot) }
    );
    renderRestoreReport(inst, srcName, r);
  } catch (e) {
    toast(`복구 실패: ${e.message}`, "err");
    box.append(el("div", { class: "empty" }, `복구 실패: ${e.message}`));
  }
}

function renderRestoreReport(inst, srcName, r) {
  const box = document.getElementById("restore-result");
  box.innerHTML = "";
  const s = r.summary || { ok: 0, skip: 0, fail: 0 };
  const head = el("div", { class: "settings-card" }, [
    el("h3", {}, `가져오기 결과 (${r.mode || "merge"}) — ${srcName} → ${inst.name}`),
    el("p", { class: "hint" },
      `생성 ${s.ok || 0} · 갱신 ${s.update || 0} · 건너뜀 ${s.skip || 0} · 실패 ${s.fail || 0}`),
  ]);
  if (r.tempPassword) {
    head.append(
      el("p", { class: "hint", style: "color:var(--warn,#d80)" },
        `복구된 사용자 임시 비밀번호: ${r.tempPassword} — 로그인 후 즉시 변경하세요.`)
    );
  }
  const rows = (r.items || []).map((it) =>
    el("tr", { class: it.status === "fail" ? "row-err" : "" }, [
      el("td", {}, it.section),
      el("td", {}, it.item),
      el("td", {}, { ok: "✓ 생성", update: "↻ 갱신", skip: "· 건너뜀", fail: "✗ 실패" }[it.status] || it.status),
      el("td", {}, it.detail || ""),
    ])
  );
  head.append(buildTable(["섹션", "항목", "결과", "상세"], rows));
  box.append(head);
  toast(
    `가져오기 완료 — 생성 ${s.ok || 0} / 갱신 ${s.update || 0} / 건너뜀 ${s.skip || 0} / 실패 ${s.fail || 0}`,
    s.fail ? "err" : "ok"
  );
  loadSettings();
}

async function loadPingConfig() {
  const form = document.getElementById("ping-form");
  if (!form) return;
  try {
    const c = await api("/api/instances/ping-config");
    form.interval.value = c.interval;
    form.warn_pct.value = c.warn_pct;
    form.crit_pct.value = c.crit_pct;
  } catch (e) {
    /* non-fatal */
  }
}

async function loadBackupConfig() {
  const form = document.getElementById("backup-form");
  if (!form) return;
  try {
    const c = await api("/api/backup-config");
    document.getElementById("backup-enabled").checked = !!c.enabled;
    document.getElementById("backup-path").value = c.path || "";
    document.getElementById("backup-time").value = c.time || "02:00";
    document.getElementById("backup-keep").value = c.keep != null ? c.keep : 14;
  } catch (e) {
    /* non-fatal */
  }
  loadBackupList();
}

async function loadBackupList() {
  const box = document.getElementById("backup-list");
  if (!box) return;
  box.innerHTML = "";
  let runs;
  try {
    runs = await api("/api/backups");
  } catch (e) {
    return;
  }
  if (!runs.length) {
    box.append(el("p", { class: "hint" }, "아직 백업이 없습니다. ‘지금 백업’으로 첫 백업을 만들 수 있습니다."));
    return;
  }
  // Each backup run is collapsed by default — click the 시각 줄을 클릭하면
  // 그 시점의 서버별 파일 목록이 펼쳐집니다.
  box.append(el("p", { class: "hint" }, `백업 ${runs.length}건 — 시각을 클릭하면 서버별 파일이 펼쳐집니다.`));
  runs.forEach((run, i) => {
    const total = run.files.reduce((a, f) => a + (f.size || 0), 0);
    const det = el("details", { class: "backup-run" });
    if (i === 0) det.open = true;   // 최신 1건만 펼쳐서 보여줌
    det.append(el("summary", {}, `${run.timestamp}  ·  파일 ${run.files.length}개  ·  ${fmtBytes(total)}`));
    const rows = run.files.map((f) => el("tr", {}, [
      el("td", {}, el("a", {
        href: `/api/backups/${encodeURIComponent(run.timestamp)}/${encodeURIComponent(f.name)}`,
        title: f.name === "_portal.json" ? "포탈 자체 설정(instances.yaml + 자동 업데이트 설정)" : f.name,
      }, f.name === "_portal.json" ? "📋 포탈 설정 (instances.yaml 등)" : f.name)),
      el("td", { class: "num" }, fmtBytes(f.size)),
    ]));
    det.append(buildTable(["파일(서버)", "크기"], rows));
    box.append(det);
  });
}

async function runBackupNow() {
  const status = document.getElementById("backup-status");
  status.textContent = "백업 중…";
  try {
    const r = await api("/api/backup-run", { method: "POST" });
    status.textContent = `백업 완료 · ${r.timestamp} · 성공 ${r.ok}/${r.total}${r.directory ? ` · 경로: ${r.directory}` : ""}`;
    const failed = (r.items || []).filter((i) => !i.ok);
    if (failed.length) {
      toast(`백업 일부 실패: ${failed.map((i) => i.name).join(", ")}`, "err");
    } else {
      toast("백업 완료");
    }
    loadBackupList();
  } catch (e) {
    status.textContent = `백업 실패: ${e.message}`;
    toast(`백업 실패: ${e.message}`, "err");
  }
}

async function loadSyncJobs() {
  const list = document.getElementById("syncjob-list");
  if (!list) return;
  // Populate source/target dropdowns from known instances.
  const opts = () => (state.instances || []).map((i) => el("option", { value: i.id }, i.name));
  const src = document.getElementById("syncjob-src");
  const tgt = document.getElementById("syncjob-tgt");
  if (src && !src.options.length) opts().forEach((o) => src.append(o));
  if (tgt && !tgt.options.length) {
    opts().forEach((o) => tgt.append(o));
    if (tgt.options.length > 1) tgt.selectedIndex = 1;
  }
  let jobs = [];
  try { jobs = (await api("/api/sync-jobs")).jobs || []; } catch (e) { return; }
  state.syncJobs = jobs;
  list.innerHTML = "";
  if (!jobs.length) {
    list.append(el("p", { class: "hint" }, "예약된 동기화 작업이 없습니다."));
    return;
  }
  const nameOf = (id) => ((state.instances || []).find((i) => i.id === id) || {}).name || id;
  const rows = jobs.map((j) => el("tr", {}, [
    el("td", {}, `${nameOf(j.source_id)} → ${nameOf(j.target_id)}`),
    el("td", {}, j.repository),
    el("td", {}, j.time),
    el("td", {}, el("label", { class: "chk" }, [
      el("input", { type: "checkbox", ...(j.enabled ? { checked: "checked" } : {}), onclick: () => toggleSyncJob(j.id) }),
      " 사용",
    ])),
    el("td", {}, [
      el("button", { onclick: () => runSyncJob(j.id) }, "지금"),
      " ",
      el("button", { class: "danger", onclick: () => deleteSyncJob(j.id) }, "삭제"),
    ]),
  ]));
  list.append(buildTable(["원본 → 대상", "저장소", "시각", "사용", ""], rows));
}

async function saveSyncJobs(jobs) {
  await api("/api/sync-jobs", { method: "PUT", body: JSON.stringify({ jobs }) });
  await loadSyncJobs();
}

async function addSyncJob() {
  const src = document.getElementById("syncjob-src").value;
  const tgt = document.getElementById("syncjob-tgt").value;
  const repo = document.getElementById("syncjob-repo").value.trim();
  const time = (document.getElementById("syncjob-time").value || "03:00").trim();
  if (!src || !tgt || !repo) { toast("원본/대상/저장소를 입력하세요.", "err"); return; }
  if (src === tgt) { toast("원본과 대상이 같습니다.", "err"); return; }
  const jobs = [...(state.syncJobs || []), { source_id: src, target_id: tgt, repository: repo, time, enabled: true }];
  try {
    await saveSyncJobs(jobs);
    document.getElementById("syncjob-repo").value = "";
    toast("동기화 작업 추가됨");
  } catch (e) { toast(`추가 실패: ${e.message}`, "err"); }
}

async function toggleSyncJob(id) {
  const jobs = (state.syncJobs || []).map((j) => j.id === id ? { ...j, enabled: !j.enabled } : j);
  try { await saveSyncJobs(jobs); } catch (e) { toast(e.message, "err"); }
}

async function deleteSyncJob(id) {
  if (!confirm("이 동기화 작업을 삭제할까요?")) return;
  const jobs = (state.syncJobs || []).filter((j) => j.id !== id);
  try { await saveSyncJobs(jobs); toast("삭제됨"); } catch (e) { toast(e.message, "err"); }
}

async function runSyncJob(id) {
  const status = document.getElementById("syncjob-status");
  status.textContent = "동기화 실행 중…";
  try {
    const r = await api(`/api/sync-jobs/run?id=${encodeURIComponent(id)}`, { method: "POST" });
    status.textContent = `완료 · 처리 ${r.processed} · 캐시 ${r.warmed} · 실패 ${r.failed}`;
    toast(`동기화 완료 — 캐시 ${r.warmed} / 실패 ${r.failed}`, r.failed ? "err" : "ok");
  } catch (e) {
    status.textContent = `실패: ${e.message}`;
    toast(`동기화 실패: ${e.message}`, "err");
  }
}

async function runDrAudit() {
  const status = document.getElementById("dr-status");
  const table = document.getElementById("dr-table");
  status.textContent = "전 서버 점검 중…";
  table.innerHTML = "";
  let r;
  try {
    r = await api("/api/dr-audit");
  } catch (e) {
    status.textContent = `점검 실패: ${e.message}`;
    return;
  }
  const c = r.counts || {};
  const cb = r.config_backup || {};
  status.textContent =
    `정상 ${c.ok || 0} · 주의 ${c.warn || 0} · 위험 ${c.crit || 0}` +
    ` | 구성 백업: ${cb.enabled ? `사용(${cb.time})` : "꺼짐 ⚠"}` +
    (cb.last_run ? ` · 마지막 ${cb.last_run}` : " · 실행 기록 없음");
  const badge = (s) => {
    const map = { ok: ["up", "정상"], warn: ["warn", "주의"], crit: ["down", "없음"], unknown: ["warn", "확인불가"] };
    const [cls, label] = map[s] || ["warn", s];
    return el("span", { class: `badge ${cls}` }, label);
  };
  const rows = (r.servers || []).map((s) => el("tr", {}, [
    el("td", {}, s.name),
    el("td", { class: "num" }, String(s.tasks ?? "—")),
    el("td", {}, fmtDate(s.last_run) || "—"),
    el("td", {}, s.last_result || "—"),
    el("td", {}, badge(s.state)),
    el("td", {}, s.error || s.detail || ""),
  ]));
  table.append(buildTable(["서버", "백업 태스크", "마지막 실행", "결과", "상태", "비고"], rows));
}

async function runDrBackups() {
  if (!confirm(
    "모든 서버에서 DB 백업 태스크('Export databases for backup')를 즉시 실행합니다.\n진행할까요?"
  )) return;
  const status = document.getElementById("dr-status");
  status.textContent = "DB 백업 실행 중…";
  try {
    const r = await api("/api/dr-run-backup", { method: "POST" });
    const servers = r.servers || [];
    const started = servers.reduce((a, s) => a + (s.started || 0), 0);
    const none = servers.filter((s) => !s.error && s.tasks === 0).map((s) => s.name);
    status.textContent = `완료 · ${started}개 백업 시작` +
      (none.length ? ` · 태스크 없는 서버: ${none.join(", ")}` : "");
    toast(`DB 백업 일괄 실행 — ${started}개 시작`, none.length ? "err" : "ok");
  } catch (e) {
    status.textContent = `실패: ${e.message}`;
  }
}

async function setReference(inst) {
  try {
    await api(`/api/instances/${encodeURIComponent(inst.id)}/reference`, { method: "POST" });
    await refreshInstances();
    // Apply immediately to the matrix (reference is evaluated client-side).
    const ref = (state.instances.find((i) => i.is_reference) || {}).id || "";
    state.matrixReference = ref;
    const sel = document.getElementById("matrix-ref");
    if (sel) sel.value = ref;
    if (state.matrix) renderMatrix();
    loadSettings();
    toast(inst.is_reference ? "기준 해제됨" : `'${inst.name}'을(를) 비교 기준으로 지정`);
  } catch (e) {
    toast(e.message, "err");
  }
}

async function settingsDelete(inst) {
  if (!confirm(`서버 '${inst.name}'을(를) 삭제하시겠습니까?`)) return;
  try {
    await api(`/api/instances/${encodeURIComponent(inst.id)}`, { method: "DELETE" });
    toast(`'${inst.name}' 삭제됨`);
    await refreshInstances();
    loadSettings();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function importSettings(file) {
  const merge = document.getElementById("import-merge").checked;
  if (!merge && !confirm("전체 교체 모드입니다. 현재 서버 목록이 가져온 내용으로 대체됩니다. 진행할까요?")) {
    return;
  }
  let text;
  try {
    text = await file.text();
  } catch (e) {
    toast("파일을 읽지 못했습니다.", "err");
    return;
  }
  try {
    await api(`/api/instances/import?mode=${merge ? "merge" : "replace"}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-yaml" },
      body: text,
    });
    toast(`가져오기 완료 (${merge ? "병합" : "전체 교체"})`);
    await refreshInstances();
    loadSettings();
  } catch (e) {
    toast(e.message, "err");
  }
}

// ---- 자동 업데이트 (포탈) -------------------------------------------------

async function loadUpdateStatus() {
  const line = document.getElementById("update-statusline");
  const logEl = document.getElementById("update-log");
  const msg = document.getElementById("update-msg");
  const srcEl = document.getElementById("update-src");
  const deployEl = document.getElementById("update-deploy");
  const edgeBox = document.getElementById("update-edge-list");
  if (!line) return;
  msg.textContent = "확인 중…";
  let r;
  try {
    r = await api("/api/update/status");
  } catch (e) {
    msg.textContent = `조회 실패: ${e.message}`;
    return;
  }
  msg.textContent = "";
  const runBtn = document.getElementById("update-run");
  if (runBtn) runBtn.disabled = !r.update_available;
  // Compact status line: 현재 · 최신 · 확인시각 · 엣지 N대 · 엣지 상태
  const latest = r.available || r.current;
  const state = r.update_available
    ? `<b style="color:var(--amber)">⬆ v${r.available} 업그레이드 가능</b>`
    : `<b style="color:var(--green)">✓ 최신</b>`;
  let edgeTxt = "";
  if (r.edges_total) {
    edgeTxt = ` · 엣지 ${r.edges_total}대 · ` + (
      r.edges_outdated || r.edges_unreachable
        ? `<b style="color:var(--amber)">구버전 ${r.edges_outdated} · 미응답 ${r.edges_unreachable}</b>`
        : `<b style="color:var(--green)">엣지 모두 최신</b>`);
  }
  line.innerHTML = `현재 <b>v${r.current}</b> · 최신 <b>v${latest}</b> ${state} · 확인 ${escapeHtml(r.checked_at || "")}${edgeTxt}`;
  if (deployEl) deployEl.innerHTML = `엣지에 보낼 배포 코드 <b>v${r.deploy_code || r.current}</b> (실행 버전과 일치)`;
  const c = r.config || {};
  if (srcEl) srcEl.textContent = c.url ? `소스: ${c.url}` : "소스 미설정 — 아래에서 URL을 입력하세요.";

  // Per-edge list (only when configured).
  if (edgeBox) {
    edgeBox.innerHTML = "";
    if ((r.edges || []).length) {
      const rows = r.edges.map((e) => el("tr", {}, [
        el("td", {}, e.url),
        el("td", {}, e.version
          ? el("span", { class: `badge ${e.outdated ? "warn" : "up"}` }, "v" + e.version + (e.outdated ? " (구버전)" : ""))
          : el("span", { class: "badge down", title: e.error || "" }, "미응답")),
      ]));
      edgeBox.append(buildTable(["엣지", "버전"], rows));
    }
  }

  const form = document.getElementById("update-form");
  if (form) {
    if (c.source) form.source.value = c.source;
    form.url.value = c.url || "";
    form.interval.value = c.interval || 60;
    form.auto_install.checked = c.auto_install !== false;
    form.edges.value = (c.edges || []).join("\n");
    form.token.value = "";
    form.token.placeholder = c.token ? "(저장된 토큰 있음 — 바꿀 때만 입력)" : "GitHub PAT 등 — 공개 소스면 비움";
  }
  if (r.remote_error) msg.textContent = `원격 확인 경고: ${r.remote_error}`;
  logEl.textContent = (r.log || []).join("\n") || "(업데이트 로그 없음)";
}

async function saveUpdateConfig(ev) {
  ev.preventDefault();
  const form = ev.target;
  const fd = new FormData(form);
  const body = {
    source: fd.get("source"),
    url: String(fd.get("url") || "").trim(),
    interval: Number(fd.get("interval")) || 60,
    auto_install: form.auto_install.checked,
    clear_token: form.clear_token.checked,
    edges: String(fd.get("edges") || "").split(/[\n,]+/).map((x) => x.trim()).filter(Boolean),
  };
  const tok = String(fd.get("token") || "");
  if (tok) body.token = tok;          // omit → keep existing
  try {
    await api("/api/update/config", { method: "POST", body: JSON.stringify(body) });
    toast("업데이트 설정을 저장했습니다");
    loadUpdateStatus();
  } catch (e) {
    toast(`저장 실패: ${e.message}`, "err");
  }
}

async function runUpdate() {
  const msg = document.getElementById("update-msg");
  if (!confirm("지금 업데이트를 적용합니다. 새 버전이 있으면 설치 후 서비스가 재시작됩니다.\n진행할까요?")) return;
  msg.textContent = "업데이트 시작 중…";
  try {
    const r = await api("/api/update/run", { method: "POST" });
    toast(r.detail || "업데이트를 시작했습니다", "ok");
    msg.textContent = "업데이트 진행 중 — 잠시 후 새로고침하세요. (서비스 재시작 시 일시적으로 끊길 수 있습니다)";
  } catch (e) {
    toast(`업데이트 실패: ${e.message}`, "err");
    msg.textContent = e.message;
  }
}

// ---- 대시보드 제목(브랜딩) -----------------------------------------------

async function loadPortalTitle() {
  try {
    const r = await api("/api/portal");
    const t = (r && r.title) || "Nexus Repository 통합 관리";
    const h = document.getElementById("app-title");
    if (h) h.textContent = t;
    document.title = t;
    const inp = document.getElementById("title-input");
    if (inp && !inp.value) inp.value = t;
  } catch (e) { /* keep the default title */ }
}

function setupPortalTitle() {
  const form = document.getElementById("title-form");
  if (!form) return;
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = document.getElementById("title-msg");
    try {
      const r = await api("/api/portal", {
        method: "PUT",
        body: JSON.stringify({ title: document.getElementById("title-input").value }),
      });
      const h = document.getElementById("app-title");
      if (h) h.textContent = r.title;
      document.title = r.title;
      document.getElementById("title-input").value = r.title;
      toast("제목을 저장했습니다");
      if (msg) msg.textContent = "";
    } catch (e) {
      if (msg) msg.textContent = e.message;
      toast(`저장 실패: ${e.message}`, "err");
    }
  });
}

// ---- 노드 계정 관리 (관리자 유저 생성 / 비번 변경) -----------------------

function fillAcctInstances() {
  const box = document.getElementById("acct-insts");
  if (!box) return;
  state.acctSel = state.acctSel || new Set();
  box.innerHTML = "";
  (state.instances || []).forEach((i) => {
    const on = state.acctSel.has(i.id);
    box.append(el("button", {
      type: "button",
      class: `pick-chip ${on ? "on" : ""}`,
      onclick: () => {
        if (state.acctSel.has(i.id)) state.acctSel.delete(i.id);
        else state.acctSel.add(i.id);
        fillAcctInstances();
      },
    }, i.name));
  });
}

function renderAcctResult(r, label) {
  const box = document.getElementById("acct-result");
  box.innerHTML = "";
  if (r.error) { box.append(el("p", { class: "site-error" }, r.error)); return; }
  box.append(el("p", { class: "hint" }, `${label} — 성공 ${r.ok}/${r.total}`));
  const rows = (r.items || []).map((it) => el("tr", {}, [
    el("td", {}, it.instance_name),
    el("td", {}, it.ok
      ? el("span", { class: "badge up" }, it.credential_synced ? "성공(자격증명 동기화)" : "성공")
      : el("span", { class: "badge down", title: it.error }, "실패")),
    el("td", { class: "site-error" }, it.ok ? "" : (it.error || "")),
  ]));
  box.append(buildTable(["서버", "결과", "오류"], rows));
}

function setupAccounts() {
  const all = document.getElementById("acct-all");
  if (all) all.addEventListener("click", () => {
    state.acctSel = new Set((state.instances || []).map((i) => i.id)); fillAcctInstances();
  });
  const none = document.getElementById("acct-none");
  if (none) none.addEventListener("click", () => { state.acctSel = new Set(); fillAcctInstances(); });

  const create = document.getElementById("acct-create");
  if (create) create.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const ids = [...(state.acctSel || [])];
    if (!ids.length) { toast("대상 서버를 선택하세요.", "err"); return; }
    const fd = new FormData(create);
    if (!confirm(`선택한 ${ids.length}개 서버에 관리자(nx-admin) 유저 '${fd.get("user_id")}'를 생성합니다.\n진행할까요?`)) return;
    try {
      const r = await api("/api/accounts/create-admin", { method: "POST", body: JSON.stringify({
        instance_ids: ids, user_id: fd.get("user_id"), password: fd.get("password"),
        first_name: fd.get("first_name") || "", email: fd.get("email") || "",
      }) });
      renderAcctResult(r, "관리자 유저 생성");
      toast(r.error ? r.error : `유저 생성 — 성공 ${r.ok}/${r.total}`, r.error || r.ok < r.total ? "err" : "ok");
    } catch (e) { toast(`실패: ${e.message}`, "err"); }
  });

  const pw = document.getElementById("acct-pw");
  if (pw) pw.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const ids = [...(state.acctSel || [])];
    if (!ids.length) { toast("대상 서버를 선택하세요.", "err"); return; }
    const fd = new FormData(pw);
    if (!confirm(`선택한 ${ids.length}개 서버에서 '${fd.get("user_id")}' 비밀번호를 변경합니다.\n(매니저 접속 계정이면 저장된 자격증명도 함께 갱신)\n진행할까요?`)) return;
    try {
      const r = await api("/api/accounts/change-password", { method: "POST", body: JSON.stringify({
        instance_ids: ids, user_id: fd.get("user_id"), password: fd.get("password"),
      }) });
      renderAcctResult(r, "비밀번호 변경");
      toast(r.error ? r.error : `비번 변경 — 성공 ${r.ok}/${r.total}`, r.error || r.ok < r.total ? "err" : "ok");
    } catch (e) { toast(`실패: ${e.message}`, "err"); }
  });
}

function setupUpdate() {
  const f = document.getElementById("update-form");
  if (f) f.addEventListener("submit", saveUpdateConfig);
  const c = document.getElementById("update-check");
  if (c) c.addEventListener("click", loadUpdateStatus);
  const r = document.getElementById("update-run");
  if (r) r.addEventListener("click", runUpdate);
}

// 서버 설정 탭을 기능별 서브 탭으로 분할(노드 관리/계정/업그레이드/모니터링/일반).
function setupSettingsSubtabs() {
  const nav = document.getElementById("settings-subtabs");
  if (!nav) return;
  const show = (sub) => {
    nav.querySelectorAll(".subtab").forEach((b) => b.classList.toggle("active", b.dataset.sub === sub));
    document.querySelectorAll("#settings .settings-card[data-sub]").forEach((c) => {
      c.style.display = c.dataset.sub === sub ? "" : "none";
    });
    state.settingsSub = sub;
  };
  nav.querySelectorAll(".subtab").forEach((b) => b.addEventListener("click", () => show(b.dataset.sub)));
  show(state.settingsSub || "nodes");
}

function setupSettings() {
  const form = document.getElementById("settings-form");
  document.getElementById("ping-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    try {
      await api("/api/instances/ping-config", {
        method: "PUT",
        body: JSON.stringify({
          interval: Number(fd.get("interval")),
          warn_pct: Number(fd.get("warn_pct")),
          crit_pct: Number(fd.get("crit_pct")),
        }),
      });
      toast("Ping 설정 저장됨");
      loadPingConfig();
    } catch (e) {
      toast(e.message, "err");
    }
  });
  document.getElementById("backup-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await api("/api/backup-config", {
        method: "PUT",
        body: JSON.stringify({
          enabled: document.getElementById("backup-enabled").checked,
          path: String(document.getElementById("backup-path").value || "").trim(),
          time: String(document.getElementById("backup-time").value || "02:00").trim(),
          keep: Number(document.getElementById("backup-keep").value) || 14,
        }),
      });
      toast("백업 설정 저장됨");
      loadBackupConfig();
    } catch (e) {
      toast(e.message, "err");
    }
  });
  document.getElementById("backup-now").addEventListener("click", runBackupNow);
  document.getElementById("dr-audit").addEventListener("click", runDrAudit);
  document.getElementById("dr-run").addEventListener("click", runDrBackups);
  document.getElementById("syncjob-add").addEventListener("click", addSyncJob);
  // "새 서버 추가" button reveals the form (add mode); 취소 hides it.
  document.getElementById("settings-add-toggle").addEventListener("click", () => {
    settingsResetForm();
    showSettingsForm(true);
    document.getElementById("settings-form-box").scrollIntoView({ behavior: "smooth" });
  });
  document.getElementById("settings-cancel").addEventListener("click", () => {
    settingsResetForm();
    showSettingsForm(false);
  });

  document.getElementById("export-btn").addEventListener("click", () => {
    window.location.href = "/api/instances/export";
  });
  const fileInput = document.getElementById("import-file");
  document.getElementById("import-btn").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) importSettings(fileInput.files[0]);
    fileInput.value = "";  // allow re-selecting the same file
  });
  const restoreInput = document.getElementById("restore-file");
  if (restoreInput) {
    restoreInput.addEventListener("change", () => {
      if (restoreInput.files && restoreInput.files[0]) applyRestoreFile(restoreInput.files[0]);
      restoreInput.value = "";  // allow re-selecting the same file
    });
  }
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const editingId = fd.get("editing_id");
    const body = {
      name: fd.get("name"),
      group: fd.get("group") || "",
      tier: Number(fd.get("tier")) || 0,
      timezone: String(fd.get("timezone") || "").trim(),
      base_url: fd.get("base_url"),
      alt_url: String(fd.get("alt_url") || "").trim(),
      username: fd.get("username") || "",
      password: fd.get("password") || "",
      verify_tls: form.verify_tls.checked,
      use_in_monitoring: form.use_in_monitoring.checked,
      use_in_comparison: form.use_in_comparison.checked,
    };
    const submit = document.getElementById("settings-submit");
    try {
      if (editingId) {
        await api(`/api/instances/${encodeURIComponent(editingId)}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        toast("변경 저장됨");
      } else {
        body.id = fd.get("id");
        // Verify the server actually responds before adding it.
        submit.disabled = true;
        submit.textContent = "연결 확인 중…";
        let test;
        try {
          test = await api("/api/instances/test", {
            method: "POST",
            body: JSON.stringify({
              base_url: body.base_url,
              username: body.username,
              password: body.password,
              verify_tls: body.verify_tls,
            }),
          });
        } catch (e) {
          test = { reachable: false, error: e.message };
        }
        submit.disabled = false;
        submit.textContent = "서버 추가";
        if (!test.reachable) {
          if (!confirm(`서버에 연결할 수 없습니다:\n${test.error || "원인 불명"}\n\n그래도 추가하시겠습니까?`)) {
            return;
          }
        }
        await api("/api/instances", { method: "POST", body: JSON.stringify(body) });
        toast(
          test.reachable
            ? `'${body.name}' 추가됨 — 연결 정상 (응답 ${test.response_ms}ms${test.repository_count != null ? ", 저장소 " + test.repository_count : ""})`
            : `'${body.name}' 추가됨 (연결 미확인)`
        );
      }
      settingsResetForm();
      showSettingsForm(false);
      await refreshInstances();
      loadSettings();
    } catch (e) {
      submit.disabled = false;
      submit.textContent = editingId ? "변경 저장" : "서버 추가";
      toast(e.message, "err");
    }
  });
}

// ---- cleanup -------------------------------------------------------------

function cleanupInst() {
  return document.getElementById("cleanup-inst").value;
}

function setupCleanup() {
  const sel = document.getElementById("cleanup-inst");
  fillInstanceSelect(sel);
  sel.addEventListener("change", loadCleanup);
  document.getElementById("cleanup-refresh").addEventListener("click", loadCleanup);
  fillInstanceSelect(document.getElementById("ca-src"));
  document.getElementById("ca-audit").addEventListener("click", runCleanupAudit);
  document.getElementById("ca-docker").addEventListener("click", runDockerGcEverywhere);
  document.getElementById("ca-compact").addEventListener("click", runCompactEverywhere);
  document.getElementById("ca-push").addEventListener("click", pushPolicyEverywhere);
  loadCleanup();
}

async function runCleanupAudit() {
  const status = document.getElementById("ca-status");
  const table = document.getElementById("ca-table");
  status.textContent = "전 서버 점검 중…";
  table.innerHTML = "";
  let r;
  try {
    r = await api("/api/cleanup-audit");
  } catch (e) {
    status.textContent = `점검 실패: ${e.message}`;
    return;
  }
  const servers = r.servers || [];
  const issues = servers.filter((s) => !s.error && (s.compact_tasks === 0 || (s.repos_without_cleanup || 0) > 0)).length;
  status.textContent = `완료 · ${servers.length}대 점검 · 조치 필요 ${issues}대`;
  const rows = servers.map((s) => {
    if (s.error) {
      return el("tr", {}, [
        el("td", {}, s.name),
        el("td", { colspan: "5", class: "url", style: "color:var(--red)" }, `조회 실패: ${s.error}`),
      ]);
    }
    const compactCell = s.compact_tasks
      ? el("span", {}, `${s.compact_tasks}개 · ${s.compact_last_result || "—"}`)
      : el("span", { class: "badge down" }, "없음 ⚠");
    const noCleanup = s.repos_without_cleanup;
    const noCleanupCell = noCleanup == null ? "—"
      : noCleanup > 0
        ? el("span", {
            class: "badge warn",
            title: (s.repos_without_cleanup_names || []).join(", "),
          }, `${noCleanup}개`)
        : "0";
    // Docker GC only matters when the server has docker repos.
    let dockerCell;
    if (!s.has_docker) dockerCell = el("span", { class: "url" }, "—");
    else if (s.docker_gc_tasks) dockerCell = el("span", {}, `${s.docker_gc_tasks}개 · ${fmtDate(s.docker_gc_last) || "미실행"}`);
    else dockerCell = el("span", { class: "badge down", title: "Docker 저장소가 있으나 GC 작업이 없어 고아 레이어가 쌓입니다" }, "없음 ⚠");
    return el("tr", {}, [
      el("td", {}, s.name),
      el("td", { class: "num" }, String(s.policies ?? "—")),
      el("td", {}, noCleanupCell),
      el("td", {}, dockerCell),
      el("td", { class: "num" }, String(s.blobstores ?? "—")),
      el("td", {}, compactCell),
      el("td", {}, fmtDate(s.compact_last) || "—"),
    ]);
  });
  table.append(buildTable(
    ["서버", "정책 수", "정책 없는 저장소", "Docker GC", "Blob store", "Compact 작업", "마지막 Compact"], rows
  ));
}

async function runDockerGcEverywhere() {
  if (!confirm(
    "모든 서버에서 'Docker - Delete unused manifests and images'(GC) 작업을 실행합니다.\n" +
    "(고아 레이어 soft-delete — 이후 Compact를 돌려야 실제 디스크가 회수됩니다)\n\n진행할까요?"
  )) return;
  const status = document.getElementById("ca-status");
  status.textContent = "Docker GC 실행 중…";
  try {
    const r = await api("/api/cleanup-docker-run", { method: "POST" });
    const servers = r.servers || [];
    const started = servers.reduce((a, s) => a + (s.started || 0), 0);
    const none = servers.filter((s) => !s.error && s.tasks === 0).map((s) => s.name);
    status.textContent = `완료 · ${started}개 GC 작업 시작` +
      (none.length ? ` · GC 작업 없는 서버: ${none.join(", ")}` : "");
    toast(`Docker GC 일괄 실행 — ${started}개 시작 (완료 후 Compact 실행)`, none.length ? "err" : "ok");
  } catch (e) {
    status.textContent = `실패: ${e.message}`;
  }
}

async function runCompactEverywhere() {
  if (!confirm(
    "모든 서버에서 'Compact blob store' 작업을 즉시 실행합니다.\n" +
    "(soft-delete된 blob을 실제로 회수 — 디스크 I/O 부하가 있으니 가급적 한가한 시간에)\n\n진행할까요?"
  )) return;
  const status = document.getElementById("ca-status");
  status.textContent = "Compact 실행 중…";
  try {
    const r = await api("/api/cleanup-compact-run", { method: "POST" });
    const servers = r.servers || [];
    const started = servers.reduce((a, s) => a + (s.started || 0), 0);
    const none = servers.filter((s) => !s.error && s.tasks === 0).map((s) => s.name);
    status.textContent = `완료 · ${started}개 작업 시작` + (none.length ? ` · 작업 없는 서버: ${none.join(", ")}` : "");
    toast(`Compact 일괄 실행 — ${started}개 작업 시작`, none.length ? "err" : "ok");
  } catch (e) {
    status.textContent = `실패: ${e.message}`;
  }
}

async function pushPolicyEverywhere() {
  const src = document.getElementById("ca-src").value;
  const name = document.getElementById("ca-policy").value.trim();
  const status = document.getElementById("ca-push-status");
  if (!src || !name) { toast("원본 서버와 정책 이름을 입력하세요.", "err"); return; }
  if (!confirm(`'${name}' 정책을 원본에서 읽어 모든 서버에 복사합니다(없는 곳만 생성). 진행할까요?`)) return;
  status.textContent = "정책 복사 중…";
  try {
    const r = await api(
      `/api/cleanup-push-policy?source_id=${encodeURIComponent(src)}&name=${encodeURIComponent(name)}`,
      { method: "POST" }
    );
    const ok = r.servers.filter((s) => s.status === "ok").length;
    const skip = r.servers.filter((s) => s.status === "skip").length;
    const fail = r.servers.filter((s) => s.status === "fail");
    status.textContent = `완료 · 생성 ${ok} · 이미 존재 ${skip} · 실패 ${fail.length}` +
      (fail.length ? ` (${fail.map((s) => s.name).join(", ")})` : "");
    toast(`정책 복사 완료 — 생성 ${ok} / 실패 ${fail.length}`, fail.length ? "err" : "ok");
  } catch (e) {
    status.textContent = `실패: ${e.message}`;
  }
}

async function loadCleanup() {
  const container = document.getElementById("cleanup-table");
  container.innerHTML = "";
  const inst = cleanupInst();
  if (!inst) return;
  let policies = [];
  try {
    policies = await api(`/api/instances/${inst}/cleanup-policies`);
  } catch (e) {
    container.append(el("div", { class: "empty" }, `정책 조회 실패: ${e.message}`));
    return;
  }
  if (!policies.length) {
    container.append(el("div", { class: "empty" }, "정리 정책이 없습니다."));
    return;
  }
  const rows = policies.map((p) =>
    el("tr", {}, [
      el("td", {}, p.name),
      el("td", {}, p.format),
      el("td", {}, JSON.stringify(p.criteria)),
      el("td", {}, p.notes || "—"),
    ])
  );
  container.append(buildTable(["이름", "포맷", "기준", "메모"], rows));
}

document.getElementById("cleanup-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!cleanupInst()) {
    toast("서버를 먼저 선택하세요.", "err");
    return;
  }
  const fd = new FormData(ev.target);
  const payload = {
    name: fd.get("name"),
    format: fd.get("format"),
    notes: fd.get("notes") || null,
  };
  const updated = fd.get("criteria_last_blob_updated");
  const downloaded = fd.get("criteria_last_downloaded");
  if (updated) payload.criteria_last_blob_updated = Number(updated);
  if (downloaded) payload.criteria_last_downloaded = Number(downloaded);

  try {
    await api(`/api/instances/${cleanupInst()}/cleanup-policies`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(`정책 '${payload.name}' 생성됨`);
    ev.target.reset();
    loadCleanup();
  } catch (e) {
    toast(e.message, "err");
  }
});

// ---- version & release notes ---------------------------------------------

const RELEASE_LABELS = {
  added: ["추가", "up"],
  changed: ["변경", "warn"],
  removed: ["삭제", "down"],
};

async function setupReleaseNotes() {
  const badge = document.getElementById("app-version");
  let data;
  try {
    data = await api("/api/release-notes");
  } catch (e) {
    badge.textContent = "";
    return;
  }
  state.releaseNotes = data;
  badge.textContent = `v${data.version}`;
  const about = document.getElementById("about-version");
  if (about) about.textContent = `v${data.version}`;
  badge.addEventListener("click", () => openReleaseNotes());

  document.getElementById("release-modal-close").addEventListener("click", () =>
    document.getElementById("release-modal").classList.add("hidden")
  );
  document.getElementById("release-modal").addEventListener("click", (ev) => {
    if (ev.target.id === "release-modal") ev.currentTarget.classList.add("hidden");
  });
}

const HISTORY_LIMIT = 5;

function renderReleaseNotesInto(container) {
  container.innerHTML = "";
  const data = state.releaseNotes;
  if (!data) { container.textContent = "이력을 불러오는 중…"; return; }
  const expanded = !!state.historyExpanded;
  const notes = expanded ? data.notes : data.notes.slice(0, HISTORY_LIMIT);
  notes.forEach((entry) => {
    container.append(el("div", { class: "rel-ver" }, [
      el("span", { class: "rel-ver-num" }, `v${entry.version}`),
      el("span", { class: "rel-ver-date" }, entry.date),
    ]));
    const list = el("ul", { class: "rel-list" });
    entry.changes.forEach((c) => {
      const [label, cls] = RELEASE_LABELS[c.type] || ["기타", ""];
      list.append(el("li", {}, [
        el("span", { class: `badge ${cls} rel-tag` }, label),
        " ",
        c.text,
      ]));
    });
    container.append(list);
  });
  if (data.notes.length > HISTORY_LIMIT) {
    container.append(el("button", {
      class: "ghost",
      onclick: () => { state.historyExpanded = !expanded; renderReleaseNotesInto(container); },
    }, expanded ? "접기 ▴" : `더 보기 (${data.notes.length - HISTORY_LIMIT}개 더) ▾`));
  }
}

function openReleaseNotes() {
  renderReleaseNotesInto(document.getElementById("release-modal-body"));
  document.getElementById("release-modal").classList.remove("hidden");
}

function renderHistory() {
  const c = document.getElementById("about-history");
  if (c) renderReleaseNotesInto(c);
}

// ---- comparison fields ---------------------------------------------------

const COMPARE_FIELD_OPTIONS = [
  ["format", "포맷"],
  ["type", "유형(hosted/proxy/group)"],
  ["remote_url", "원격 URL(프록시)"],
  ["online", "온라인 상태"],
];

function renderCompareFields(selected) {
  const c = document.getElementById("compare-fields");
  if (!c) return;
  c.innerHTML = "";
  COMPARE_FIELD_OPTIONS.forEach(([key, label]) => {
    const cb = el("input", { type: "checkbox" });
    cb.checked = selected.includes(key);
    cb.dataset.field = key;
    cb.addEventListener("change", saveCompareFields);
    c.append(el("label", { class: "chk" }, [cb, " ", label]));
  });
}

async function loadCompareFields() {
  try {
    const r = await api("/api/instances/compare-fields");
    state.compareFields = r.fields || [];
    renderCompareFields(state.compareFields);
  } catch (e) {
    /* non-fatal */
  }
}

async function saveCompareFields() {
  const fields = [...document.querySelectorAll("#compare-fields input:checked")]
    .map((cb) => cb.dataset.field);
  try {
    const r = await api("/api/instances/compare-fields", {
      method: "PUT",
      body: JSON.stringify({ fields }),
    });
    state.compareFields = r.fields || fields;
    toast("비교 기준 저장됨");
    if (state.matrix) renderMatrix();  // re-evaluate drift live
  } catch (e) {
    toast(e.message, "err");
  }
}

// ---- group display order -------------------------------------------------

function renderGroupOrderList(groups) {
  const c = document.getElementById("group-order");
  if (!c) return;
  c.innerHTML = "";
  if (!groups.length) {
    c.append(el("div", { class: "empty" }, "그룹이 없습니다. 서버에 그룹을 지정하세요."));
    return;
  }
  const list = el("div", { class: "grouporder-list" });
  groups.forEach((g, i) => {
    list.append(el("div", { class: "grouporder-row" }, [
      el("span", { class: "go-rank" }, `${i + 1}.`),
      el("span", { class: "go-name" }, g),
      el("span", { class: "go-btns" }, [
        el("button", i === 0 ? { disabled: "true" } : { onclick: () => moveGroupOrder(groups, i, -1) }, "▲"),
        el("button", i === groups.length - 1 ? { disabled: "true" } : { onclick: () => moveGroupOrder(groups, i, 1) }, "▼"),
      ]),
    ]));
  });
  c.append(list);
}

async function loadGroupOrder() {
  try {
    const r = await api("/api/instances/group-order");
    state.groupOrder = r.groups || [];
    renderGroupOrderList(r.groups || []);
  } catch (e) {
    const c = document.getElementById("group-order");
    if (c) c.textContent = "";
  }
}

async function moveGroupOrder(groups, idx, delta) {
  const j = idx + delta;
  if (j < 0 || j >= groups.length) return;
  const next = groups.slice();
  [next[idx], next[j]] = [next[j], next[idx]];
  try {
    const r = await api("/api/instances/group-order", {
      method: "PUT",
      body: JSON.stringify({ groups: next }),
    });
    renderGroupOrderList(r.groups || next);
    loadOverview();  // refresh the (possibly hidden) overview ordering
    toast("그룹 순서 저장됨");
  } catch (e) {
    toast(e.message, "err");
  }
}

// ---- bulk apply (저장소 설정 일괄 변경) ------------------------------------

function fillBulkInstances() {
  const sel = document.getElementById("bulk-inst");
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = "";
  (state.instances || []).forEach((i) => sel.append(el("option", { value: i.id }, i.name)));
  if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
}

async function loadBulkFields() {
  const sel = document.getElementById("bulk-inst");
  const status = document.getElementById("bulk-status");
  const table = document.getElementById("bulk-table");
  document.getElementById("bulk-result").innerHTML = "";
  if (!sel.value) { toast("서버를 선택하세요.", "err"); return; }
  status.textContent = "모든 저장소 설정 읽는 중…";
  table.innerHTML = "";
  try {
    const r = await api(`/api/bulk/fields?instance_id=${encodeURIComponent(sel.value)}`);
    state.bulkFields = r;
    const errN = Object.keys(r.errors || {}).length;
    status.textContent =
      `저장소 ${r.loaded}/${r.repos}개 읽음 · 설정 항목 ${r.fields.length}개` +
      (errN ? ` · 읽기 실패 ${errN}` : "");
    renderBulkTable();
  } catch (e) {
    status.textContent = "";
    table.append(el("div", { class: "empty" }, `설정 읽기 실패: ${e.message}`));
  }
}

// Booleans get a true/false select; everything else a free-text input.
// The input is JSON-parsed on apply, so numbers/true/false/plain text all work.
function bulkValueEditor(f) {
  if (f.all_bool) {
    return el("select", {}, [
      el("option", { value: "true" }, "true"),
      el("option", { value: "false" }, "false"),
    ]);
  }
  const common = Object.entries(f.values || {}).sort((a, b) => b[1] - a[1])[0];
  return el("input", {
    type: "text",
    placeholder: common ? common[0] : "",
    style: "min-width:140px",
  });
}

function renderBulkTable() {
  const table = document.getElementById("bulk-table");
  if (!table) return;
  table.innerHTML = "";
  const data = state.bulkFields;
  if (!data) return;
  const q = (document.getElementById("bulk-filter").value || "").trim().toLowerCase();
  let fields = data.fields || [];
  if (q) fields = fields.filter((f) => f.key.toLowerCase().includes(q));
  if (!fields.length) {
    table.append(el("div", { class: "empty" }, "표시할 설정 항목이 없습니다."));
    return;
  }
  const thead = el("thead", {}, el("tr", {}, [
    el("th", {}, "설정 항목"),
    el("th", {}, "현재 값 분포"),
    el("th", {}, "저장소 수"),
    el("th", {}, "새 값"),
    el("th", {}, ""),
  ]));
  const rows = fields.map((f) => {
    const dist = Object.entries(f.values || {}).sort((a, b) => b[1] - a[1]);
    const shown =
      dist.slice(0, 4).map(([v, c]) => `${v} ×${c}`).join(" · ") +
      (dist.length > 4 ? ` · 외 ${dist.length - 4}종` : "");
    const editor = bulkValueEditor(f);
    const btn = el("button", {
      type: "button",
      onclick: () => applyBulkField(f, editor.value),
    }, "적용");
    return el("tr", {}, [
      el("td", {}, el("code", {}, f.key)),
      el("td", {}, shown),
      el("td", {}, String(f.repos)),
      el("td", {}, editor),
      el("td", {}, btn),
    ]);
  });
  table.append(el("table", {}, [thead, el("tbody", {}, rows)]));
}

async function applyBulkField(f, raw) {
  if (String(raw).trim() === "") { toast("새 값을 입력하세요.", "err"); return; }
  const sel = document.getElementById("bulk-inst");
  const inst = (state.instances || []).find((i) => i.id === sel.value);
  const name = inst ? inst.name : sel.value;
  let value;
  try { value = JSON.parse(raw); } catch (_) { value = raw; }
  if (!confirm(
    `'${name}' 서버에서 이 항목을 가진 모든 저장소(${f.repos}개)에 적용합니다.\n\n` +
    `${f.key} = ${JSON.stringify(value)}\n\n진행할까요?`
  )) return;
  const status = document.getElementById("bulk-status");
  status.textContent = `적용 중… (${f.key})`;
  try {
    const r = await api("/api/bulk/apply", {
      method: "POST",
      body: JSON.stringify({ instance_id: sel.value, key: f.key, value }),
    });
    const c = r.counts || {};
    toast(
      `일괄 적용 완료 — 변경 ${c.ok || 0} · 건너뜀 ${c.skip || 0} · 실패 ${c.fail || 0}`,
      c.fail ? "err" : "ok"
    );
    await loadBulkFields();   // refresh the value distribution
    renderBulkResult(r);
    // Server configs changed — invalidate matrix-derived caches.
    state.slaveDiffCache = {}; state.repoCfgCache = {}; state.slaveCache = {};
  } catch (e) {
    status.textContent = "";
    toast(`일괄 적용 실패: ${e.message}`, "err");
  }
}

function renderBulkResult(r) {
  const box = document.getElementById("bulk-result");
  box.innerHTML = "";
  const fails = (r.items || []).filter((it) => it.status === "fail");
  if (!fails.length) return;
  box.append(el("div", { class: "settings-card", style: "margin:10px 0" }, [
    el("h3", {}, `실패 ${fails.length}건 — ${r.key}`),
    ...fails.map((it) =>
      el("p", { class: "site-error", style: "margin:2px 0" }, `${it.repository}: ${it.detail}`)),
  ]));
}

function setupBulk() {
  document.getElementById("bulk-load").addEventListener("click", loadBulkFields);
  document.getElementById("bulk-filter").addEventListener("input", renderBulkTable);
}

// ---- bootstrap -----------------------------------------------------------

async function init() {
  setupAuth();
  loadPortalTitle();          // public — show the custom title even before login
  let publicMode = false;
  try {
    const st = await api("/api/auth-status");
    if (st.required && !st.authenticated) publicMode = true;
    else if (st.required) document.getElementById("logout-btn").classList.remove("hidden");
  } catch (e) { /* auth-status unavailable — proceed */ }
  state.publicMode = publicMode;
  if (publicMode) {
    enterPublicMode();
  } else {
    try {
      state.instances = await api("/api/instances");
    } catch (e) {
      toast(`인스턴스 목록 로드 실패: ${e.message}`, "err");
      return;
    }
  }
  setupRepositories();
  setupCleanup();
  setupCompare();
  setupDownloads();
  setupTasks();
  setupSecurity();
  setupSettings();
  setupSettingsSubtabs();
  setupPortalTitle();
  setupAccounts();
  setupUpdate();
  setupBulk();
  setupTopology();
  setupAlerts();
  setupInfra();
  setupSearch();
  document.getElementById("df-refresh").addEventListener("click", () => loadDiskForecast(true));
  document.getElementById("dc-days").addEventListener("change", loadDiskCharts);
  document.getElementById("cc-run").addEventListener("click", loadCleanupCandidates);
  setupReleaseNotes();
  loadOverviewTree();   // 개요 (계위 상황판)
  loadOverview();       // 인스턴스 상태 카드
  if (!publicMode) loadMatrix();   // /api/matrix needs auth
  // Keep the current screen across a page refresh (URL hash).
  restoreActiveTab();
}

init();
