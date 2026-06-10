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
  if (!res.ok) {
    throw new Error(formatApiError(body.detail, res.status));
  }
  return body;
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
    if (tab.dataset.tab === "blobstore") loadBlobstores();
    if (tab.dataset.tab === "metrics") loadMetrics();
    if (tab.dataset.tab === "infra") loadInfra();
    if (tab.dataset.tab === "overview") loadOverview();
    if (tab.dataset.tab === "about") renderHistory();
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

  // 2) Fetch the real status + group order, then re-render with data.
  let statuses, order;
  try {
    const [st, ord] = await Promise.all([
      api("/api/status"),
      api("/api/instances/group-order"),
    ]);
    statuses = st;
    order = (ord && ord.groups) || [];
    state.groupOrder = order;
  } catch (e) {
    cards.innerHTML = "";
    cards.append(el("div", { class: "empty" }, `상태를 불러올 수 없습니다: ${e.message}`));
    return;
  }
  if (!statuses.length) {
    cards.innerHTML = "";
    cards.append(el("div", { class: "empty" }, "구성된 인스턴스가 없습니다. instances.yaml을 확인하세요."));
    return;
  }
  renderStatusCards(statuses, order);
}

function renderStatusCards(items, order) {
  const cards = document.getElementById("status-cards");
  cards.innerHTML = "";

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
    tip.textContent = `${best.p.v} ${unit} · ${new Date(best.p.t * 1000).toLocaleString()}`;
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

function visibleMatrixColumns() {
  const m = state.matrix;
  if (!m) return [];
  return state.matrixCols ? m.columns.filter((c) => state.matrixCols.has(c.id)) : m.columns;
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
  m.columns.forEach((col) => {
    const on = !state.matrixCols || state.matrixCols.has(col.id);
    instBox.append(el("button", {
      type: "button",
      class: `pick-chip ${on ? "on" : ""}`,
      onclick: () => toggleMatrixPick("matrixCols", col.id),
    }, col.reachable ? col.name : `${col.name} ⚠`));
  });
  repoBox.innerHTML = "";
  m.rows.forEach((r) => {
    const on = !state.matrixRepos || state.matrixRepos.has(r.repository);
    repoBox.append(el("button", {
      type: "button",
      class: `pick-chip ${on ? "on" : ""}`,
      onclick: () => toggleMatrixPick("matrixRepos", r.repository),
    }, r.repository));
  });
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
  state.matrixRepos = on ? new Set(m.rows.map((r) => r.repository)) : new Set();
  renderMatrixPickers();
  renderMatrix();
}

function matrixColName(id) {
  const m = state.matrix;
  const c = m && m.columns.find((x) => x.id === id);
  return c ? c.name : id;
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

// A "slave" cell is a proxy whose remote URL points at one of our managed
// servers (its master). Such a cell is the expected master/slave setup, not a
// configuration drift, so it is treated as normal in the matrix.
function cellIsSlave(c) {
  if (!c || !c.remote_url) return false;
  const h = hostOf(c.remote_url);
  return !!h && (state.instances || []).some((i) => hostOf(i.base_url) === h);
}

function masterNameForCell(c) {
  const h = c && c.remote_url ? hostOf(c.remote_url) : "";
  const m = h && (state.instances || []).find((i) => hostOf(i.base_url) === h);
  return m ? m.name : "";
}

// Keys that differ between two repo configs, ignoring host-specific fields
// (the proxy remote URL, the repo URL, and the name). Empty array = identical
// apart from those, i.e. a clean master/slave mirror.
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
  keys.forEach((k) => { if (ma[k] !== mb[k]) diffs.push(k); });
  return diffs.sort();
}

// Resolve (and cache) a slave cell's relationship to its master: which master,
// which repo, and whether anything beyond remoteUrl differs (with the keys).
async function ensureSlaveInfo(repo, col, c) {
  const key = `${col.id}:${repo}`;
  state.slaveDiffCache = state.slaveDiffCache || {};
  if (key in state.slaveDiffCache) return state.slaveDiffCache[key];
  const h = c && c.remote_url ? hostOf(c.remote_url) : "";
  const master = h
    ? (state.instances || []).find((i) => i.id !== col.id && hostOf(i.base_url) === h)
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

  let suffix;
  let cls = "";
  if (info.unverified) {
    suffix = " · 마스터 설정 확인 불가";
  } else if (info.differs) {
    cls = "diff";
    suffix = ` · 다른 항목: ${info.keys.join(", ")}`;
  } else {
    suffix = " · 설정 동일 (remoteUrl만 다름)";
  }
  const note =
    `<div class="mtip-slave ${cls}">` +
    `<div class="mtip-slave-name">⛓ ${escapeHtml(info.master.name)}</div>` +
    `<div class="mtip-slave-tag">Slave${info.differs ? " · 설정 다름" : ""}</div>` +
    `<div class="mtip-sub">→ ${escapeHtml(info.mRepo)}${escapeHtml(suffix)}</div>` +
    `</div>`;
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
  toast(`'${repo}' 설정 복사 중… (${sName} → ${tName})`);
  try {
    const r = await api(
      `/api/matrix/copy-repo?repository=${encodeURIComponent(repo)}` +
        `&source_id=${encodeURIComponent(src.inst)}&target_id=${encodeURIComponent(inst)}`,
      { method: "POST" }
    );
    const it = (r.items && r.items[0]) || {};
    if (it.status === "fail") {
      toast(`복사 실패: ${it.detail || "원인 불명"}`, "err");
    } else {
      toast(`'${repo}' 복사 완료 — ${it.status === "update" ? "갱신" : "생성"} (${tName})`);
    }
    await loadMatrix();
  } catch (err) {
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
    headCells.push(el("th", { class: col.id === refId ? "ref-col" : "", title: col.error || col.name }, label));
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
      // remoteUrl differs it is normal (✓ "<master> Slave"); if other settings
      // differ it is a real drift (≠ "<master> Slave·다름").
      if (present && cellIsSlave(c)) {
        const mn = masterNameForCell(c);
        const sd = (state.slaveDiffCache || {})[`${col.id}:${row.repository}`];
        if (sd && sd.differs) {
          cls = "drift"; mark = "≠";
          meta = `${mn ? `${mn} ` : ""}Slave·설정 다름`;
        } else {
          cls = "consistent"; mark = "✓";
          meta = `${mn ? `${mn} ` : ""}Slave${sd && sd.unverified ? "?" : ""}`;
        }
      }
      const inner = el("span", { class: `mcell ${cls}` }, [
        el("span", { class: "mark" }, mark),
        meta ? el("span", { class: "meta" }, meta) : null,
      ]);
      const cell = c;
      const td = el("td", {
        class: `mdrop ${refMark}`,
        draggable: present ? "true" : "false",
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
    const [matrix, cf] = await Promise.all([
      api("/api/matrix"),
      api("/api/instances/compare-fields"),
    ]);
    state.matrix = matrix;
    state.compareFields = (cf && cf.fields) || [];
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
document.getElementById("matrix-ref").addEventListener("change", (e) => {
  state.matrixReference = e.target.value;
  renderMatrix();
});
document.getElementById("matrix-repo-all").addEventListener("click", () => setAllMatrixRepos(true));
document.getElementById("matrix-repo-none").addEventListener("click", () => setAllMatrixRepos(false));

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
  form.base_url.value = inst.base_url;
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
      el("td", {}, i.group || "—"),
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
  container.append(buildTable(
    ["이름", "식별자", "그룹", "주소", "계정", "모니터링", "비교", "기준", ""], rows
  ));
  loadGroupOrder();
  loadCompareFields();
  loadPingConfig();
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
  loadCleanup();
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

// ---- bootstrap -----------------------------------------------------------

async function init() {
  try {
    state.instances = await api("/api/instances");
  } catch (e) {
    toast(`인스턴스 목록 로드 실패: ${e.message}`, "err");
    return;
  }
  setupRepositories();
  setupCleanup();
  setupCompare();
  setupDownloads();
  setupTasks();
  setupSecurity();
  setupSettings();
  setupTopology();
  setupAlerts();
  setupInfra();
  setupReleaseNotes();
  loadOverview();
  loadMatrix();
}

init();
