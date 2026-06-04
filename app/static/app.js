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
};

// ---- helpers -------------------------------------------------------------

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `요청 실패 (${res.status})`);
  }
  return body;
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

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
    // Lazy-load tabs that need it (downloads is started manually via 시작).
    if (tab.dataset.tab === "tasks" && !state.tasksLoaded) {
      state.tasksLoaded = true;
      loadTasks();
    }
    if (tab.dataset.tab === "security" && !state.securityLoaded) {
      state.securityLoaded = true;
      loadSecurity();
    }
    if (tab.dataset.tab === "alerts") {
      loadAlerts();
    }
    if (tab.dataset.tab === "content" && !state.contentSetup) {
      state.contentSetup = true;
      setupContent();
    }
    if (tab.dataset.tab === "settings") {
      loadSettings();
    }
    if (tab.dataset.tab === "topology" && !state.topologyLoaded) {
      state.topologyLoaded = true;
      loadTopology();
    }
  });
});

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

async function loadOverview() {
  const cards = document.getElementById("status-cards");
  cards.innerHTML = "";
  let statuses = [];
  try {
    statuses = await api("/api/status");
  } catch (e) {
    cards.append(el("div", { class: "empty" }, `상태를 불러올 수 없습니다: ${e.message}`));
    return;
  }
  if (!statuses.length) {
    cards.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다. instances.yaml을 확인하세요."));
    return;
  }
  statuses.forEach((s) => {
    let badge;
    if (!s.reachable) badge = el("span", { class: "badge down status-badge", title: "클릭하여 원인 보기", onclick: () => openStatusDetail(s) }, "연결 불가");
    else if (!s.healthy) badge = el("span", { class: "badge warn status-badge", title: "클릭하여 원인 보기", onclick: () => openStatusDetail(s) }, "주의");
    else badge = el("span", { class: "badge up status-badge", title: "클릭하여 점검 상세 보기", onclick: () => openStatusDetail(s) }, "정상");

    const metrics = el("div", { class: "metrics" }, [
      el("div", { class: "metric" }, [
        el("div", { class: "label" }, "응답시간"),
        el("div", { class: "value" }, s.response_ms != null ? `${s.response_ms} ms` : "—"),
      ]),
      el("div", { class: "metric" }, [
        el("div", { class: "label" }, "저장소"),
        el("div", { class: "value" }, s.repository_count != null ? s.repository_count : "—"),
      ]),
    ]);

    const card = el("div", { class: "card" }, [
      el("div", { class: "name" }, [s.name, " ", badge]),
      el("div", { class: "url" }, s.base_url),
      metrics,
    ]);
    if (s.error) card.append(el("div", { class: "url", style: "color:var(--red);margin-top:8px" }, s.error));
    cards.append(card);
  });

  loadBlobstores();
  loadMetrics();
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

async function loadBlobstores() {
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

// ---- topology ------------------------------------------------------------

function setupTopology() {
  document.getElementById("topo-refresh").addEventListener("click", loadTopology);
  document.getElementById("topo-probe").addEventListener("change", loadTopology);
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
    const statusBadge = node.reachable
      ? el("span", { class: "badge up" }, "정상")
      : el("span", { class: "badge down" }, "다운");
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
  return `${c.format || ""}|${c.type || ""}|${c.remote_url || ""}`;
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
    columns.forEach((col) => {
      const c = row.cells[col.id];
      matches[col.id] = c && c.present ? !!c.matches_reference : null;
    });
    return { status: row.status, matches, refMissing: false };
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
    if (c && c.present) {
      const m = cellSignature(c) === refSig;
      matches[col.id] = m;
      if (!m) anyDiff = true;
    } else {
      matches[col.id] = null;
    }
  });

  let status;
  if (anyDiff) status = "drift";
  else if (presentCount < reachable.length) status = "partial";
  else status = "consistent";
  return { status, matches, refMissing: false };
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

  const refId = state.matrixReference || "";
  const evals = new Map();
  matrix.rows.forEach((r) => evals.set(r, evaluateRow(r, matrix.columns, refId)));

  const driftOnly = document.getElementById("drift-only").checked;
  let rows = matrix.rows;
  if (driftOnly) rows = rows.filter((r) => evals.get(r).status !== "consistent");

  if (!rows.length) {
    container.append(el("div", { class: "empty" },
      driftOnly ? "차이가 있는 저장소가 없습니다. 모두 일치합니다 ✓" : "저장소가 없습니다."));
    return;
  }

  // Header: blank corner + one column per instance (with unreachable mark).
  const headCells = [el("th", { class: "rowhead" }, "저장소 \\ 인스턴스")];
  matrix.columns.forEach((col) => {
    let label = col.reachable ? col.name : `${col.name} ⚠`;
    if (col.id === refId) label = `${label} (기준)`;
    headCells.push(el("th", { class: col.id === refId ? "ref-col" : "", title: col.error || col.name }, label));
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const body = rows.map((row) => {
    const ev = evals.get(row);
    const refCell = referenceCell(row, matrix.columns, refId);
    const refLabel = refId
      ? ((matrix.columns.find((c) => c.id === refId) || {}).name || "기준")
      : "다수 기준";
    const tds = [
      el("td", { class: "rowhead" }, [
        el("span", { class: "link", title: "설정 자세히 비교", onclick: () => openRepoDiff(row.repository) }, row.repository),
        rowStatusBadge(ev.status),
      ]),
    ];
    matrix.columns.forEach((col) => {
      const c = row.cells[col.id] || { present: false };
      const match = ev.matches[col.id];
      let cls, mark, meta;
      if (c.unknown) { cls = "unknown"; mark = "?"; meta = ""; }
      else if (!c.present) { cls = "missing"; mark = "—"; meta = ""; }
      else if (match === null) { cls = "neutral"; mark = "•"; meta = c.format || ""; }
      else if (match) { cls = "consistent"; mark = "✓"; meta = c.format || ""; }
      else { cls = "drift"; mark = "≠"; meta = [c.type, c.remote_url].filter(Boolean).join(" · ") || c.format || ""; }

      let title = cellDetail(c);
      if (cls === "drift" && refCell) {
        title = `기준(${refLabel}): ${cellValueText(refCell)}\n이 서버(${col.name}): ${cellValueText(c)}`;
      }
      const refMark = col.id === refId ? "ref-col" : "";
      const inner = el("span", { class: `mcell ${cls}`, title }, [
        el("span", { class: "mark" }, mark),
        meta ? el("span", { class: "meta" }, meta) : null,
      ]);
      tds.push(el("td", { class: refMark }, inner));
    });
    return el("tr", {}, tds);
  });

  const table = el("table", { class: "matrix" }, [thead, el("tbody", {}, body)]);
  container.append(table);
}

function populateMatrixRef() {
  const sel = document.getElementById("matrix-ref");
  // Default to the designated reference server (from 서버 설정), if any.
  const designated = (state.instances.find((i) => i.is_reference) || {}).id || "";
  const prev = state.matrixReference || designated || "";
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "(자동: 다수 기준)"));
  (state.matrix ? state.matrix.columns : []).forEach((col) =>
    sel.append(el("option", { value: col.id }, col.name))
  );
  sel.value = [...sel.options].some((o) => o.value === prev) ? prev : "";
  state.matrixReference = sel.value;
}

async function loadMatrix() {
  const container = document.getElementById("matrix-table");
  try {
    state.matrix = await api("/api/matrix");
  } catch (e) {
    container.innerHTML = "";
    container.append(el("div", { class: "empty" }, `매트릭스 로드 실패: ${e.message}`));
    return;
  }
  populateMatrixRef();
  renderMatrix();
}

document.getElementById("drift-only").addEventListener("change", renderMatrix);
document.getElementById("matrix-ref").addEventListener("change", (e) => {
  state.matrixReference = e.target.value;
  renderMatrix();
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
    headCells.push(el("th", { title: col.error || col.name }, label));
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
}

async function openRepoDiff(name) {
  document.getElementById("repo-modal-title").textContent = `저장소 설정 비교 — ${name}`;
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
    repos.forEach((r) =>
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

async function loadRepositories() {
  const container = document.getElementById("repo-table");
  container.innerHTML = "";
  document.getElementById("component-heading").classList.add("hidden");
  document.getElementById("component-table").innerHTML = "";
  document.getElementById("component-pager").classList.add("hidden");
  if (!state.current) return;

  let repos = [];
  try {
    repos = await api(`/api/instances/${state.current}/repositories`);
  } catch (e) {
    container.append(el("div", { class: "empty" }, `저장소 조회 실패: ${e.message}`));
    return;
  }
  if (!repos.length) {
    container.append(el("div", { class: "empty" }, "저장소가 없습니다."));
    return;
  }
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
    await api(`/api/instances/${state.current}/repositories/${encodeURIComponent(name)}`, {
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

  let url = `/api/instances/${state.current}/components?repository=${encodeURIComponent(repo)}`;
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
    await api(`/api/instances/${state.current}/components/${encodeURIComponent(id)}`, {
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
    repos.forEach((r) =>
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
  const rows = list.map((s) => {
    if (!s.reachable) {
      return el("tr", {}, [
        el("td", {}, s.name),
        el("td", { colspan: "4", class: "site-error" }, `조회 불가: ${s.error || ""}`),
      ]);
    }
    const adminList = s.admin_users && s.admin_users.length
      ? s.admin_users.join(", ")
      : "—";
    return el("tr", {}, [
      el("td", {}, s.name),
      el("td", {}, yesNoBadge(s.anonymous_enabled, true, ["허용", "차단"])),
      el("td", {}, yesNoBadge(s.admin_active, true, ["활성", "비활성"])),
      el("td", { title: adminList }, `${s.admin_users ? s.admin_users.length : "—"}${adminList !== "—" ? " (" + adminList + ")" : ""}`),
      el("td", { class: "num" }, s.user_count != null ? s.user_count.toLocaleString() : "—"),
    ]);
  });
  container.append(buildTable(
    ["서버", "익명 접근", "기본 admin 계정", "관리자 권한 계정", "사용자 수"], rows
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

const SETTINGS_SELECTORS = ["cmp-left-inst", "cmp-right-inst", "dl-inst", "task-inst"];

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

function settingsResetForm() {
  const form = document.getElementById("settings-form");
  form.reset();
  form.editing_id.value = "";
  form.id.disabled = false;
  form.use_in_monitoring.checked = true;
  form.use_in_comparison.checked = true;
  document.getElementById("settings-form-title").textContent = "새 서버 추가";
  document.getElementById("settings-submit").textContent = "서버 추가";
  document.getElementById("settings-cancel").classList.add("hidden");
}

function settingsEdit(inst) {
  const form = document.getElementById("settings-form");
  form.editing_id.value = inst.id;
  form.id.value = inst.id;
  form.id.disabled = true;                 // id is the key; not editable
  form.name.value = inst.name;
  form.base_url.value = inst.base_url;
  form.username.value = inst.username || "";
  form.password.value = "";                // blank = keep existing
  form.verify_tls.checked = inst.verify_tls === true;
  form.use_in_monitoring.checked = inst.use_in_monitoring !== false;
  form.use_in_comparison.checked = inst.use_in_comparison !== false;
  document.getElementById("settings-form-title").textContent = `서버 수정 — ${inst.name}`;
  document.getElementById("settings-submit").textContent = "변경 저장";
  document.getElementById("settings-cancel").classList.remove("hidden");
  document.getElementById("settings-form").scrollIntoView({ behavior: "smooth" });
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
    base_url: inst.base_url,
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
  const rows = list.map((i) =>
    el("tr", {}, [
      el("td", {}, i.name),
      el("td", {}, i.id),
      el("td", {}, i.base_url),
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
        el("button", { class: "danger", onclick: () => settingsDelete(i) }, "삭제"),
      ]),
    ])
  );
  container.append(buildTable(
    ["이름", "식별자", "주소", "계정", "모니터링", "비교", "기준", ""], rows
  ));
  renderHistory();
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

function setupSettings() {
  const form = document.getElementById("settings-form");
  document.getElementById("settings-cancel").addEventListener("click", settingsResetForm);

  document.getElementById("export-btn").addEventListener("click", () => {
    window.location.href = "/api/instances/export";
  });
  const fileInput = document.getElementById("import-file");
  document.getElementById("import-btn").addEventListener("click", () => fileInput.click());
  document.getElementById("history-btn").addEventListener("click", openReleaseNotes);
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) importSettings(fileInput.files[0]);
    fileInput.value = "";  // allow re-selecting the same file
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const editingId = fd.get("editing_id");
    const body = {
      name: fd.get("name"),
      base_url: fd.get("base_url"),
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

async function loadCleanup() {
  const container = document.getElementById("cleanup-table");
  container.innerHTML = "";
  if (!state.current) return;
  let policies = [];
  try {
    policies = await api(`/api/instances/${state.current}/cleanup-policies`);
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
  if (!state.current) {
    toast("인스턴스를 먼저 선택하세요.", "err");
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
    await api(`/api/instances/${state.current}/cleanup-policies`, {
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
  badge.addEventListener("click", () => openReleaseNotes());

  document.getElementById("release-modal-close").addEventListener("click", () =>
    document.getElementById("release-modal").classList.add("hidden")
  );
  document.getElementById("release-modal").addEventListener("click", (ev) => {
    if (ev.target.id === "release-modal") ev.currentTarget.classList.add("hidden");
  });
  renderHistory();  // fill the 서버 설정 History section if present
}

function renderReleaseNotesInto(container) {
  container.innerHTML = "";
  const data = state.releaseNotes;
  if (!data) { container.textContent = "이력을 불러오는 중…"; return; }
  data.notes.forEach((entry) => {
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
}

function openReleaseNotes() {
  renderReleaseNotesInto(document.getElementById("release-modal-body"));
  document.getElementById("release-modal").classList.remove("hidden");
}

function renderHistory() {
  const c = document.getElementById("settings-history");
  if (c) renderReleaseNotesInto(c);
}

// ---- bootstrap -----------------------------------------------------------

function refreshActiveTab() {
  loadOverview();
  loadMatrix();
  loadRepositories();
  loadCleanup();
}

async function init() {
  try {
    state.instances = await api("/api/instances");
  } catch (e) {
    toast(`인스턴스 목록 로드 실패: ${e.message}`, "err");
    return;
  }
  const select = document.getElementById("instance-select");
  select.innerHTML = "";
  state.instances.forEach((i) => {
    select.append(el("option", { value: i.id }, i.name));
  });
  if (state.instances.length) {
    state.current = state.instances[0].id;
  }
  select.addEventListener("change", () => {
    state.current = select.value;
    refreshActiveTab();
  });
  document.getElementById("refresh-btn").addEventListener("click", refreshActiveTab);
  setupCompare();
  setupDownloads();
  setupTasks();
  setupSecurity();
  setupSettings();
  setupTopology();
  setupAlerts();
  setupReleaseNotes();
  refreshActiveTab();
}

init();
