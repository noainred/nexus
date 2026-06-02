"use strict";

const state = {
  instances: [],
  current: null,
  componentToken: null,
  componentRepo: null,
  matrix: null,
  repoDiff: null,
  compareDiff: null,
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
  });
});

// ---- overview ------------------------------------------------------------

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
    if (!s.reachable) badge = el("span", { class: "badge down" }, "연결 불가");
    else if (!s.healthy) badge = el("span", { class: "badge warn" }, "주의");
    else badge = el("span", { class: "badge up" }, "정상");

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
          el("td", { colspan: "5", class: "site-error" }, `조회 불가: ${site.error || ""}`),
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
          el("td", { colspan: "5", class: "empty" }, "Blob store 없음"),
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
          el("td", {}, fmtBytes(b.total_size_bytes)),
          el("td", {}, fmtBytes(b.available_space_bytes)),
          el("td", {}, b.blob_count != null ? b.blob_count.toLocaleString() : "—"),
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
          el("td", {}, fmtBytes(site.total_size_bytes)),
          el("td", {}, ""),
          el("td", {}, site.blob_count != null ? site.blob_count.toLocaleString() : "—"),
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
      el("td", {}, fmtBytes(grandUsed)),
      el("td", {}, ""),
      el("td", {}, grandBlobs.toLocaleString()),
    ])
  );

  container.append(
    buildTable(["사이트", "Blob Store", "유형", "사용량", "가용 공간", "Blob 수"], rows)
  );
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
  };
  const [cls, label] = map[status] || ["warn", status];
  return el("span", { class: `badge ${cls} row-status` }, label);
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

  const driftOnly = document.getElementById("drift-only").checked;
  let rows = matrix.rows;
  if (driftOnly) rows = rows.filter((r) => r.status !== "consistent");

  if (!rows.length) {
    container.append(el("div", { class: "empty" },
      driftOnly ? "차이가 있는 저장소가 없습니다. 모두 일치합니다 ✓" : "저장소가 없습니다."));
    return;
  }

  // Header: blank corner + one column per instance (with unreachable mark).
  const headCells = [el("th", { class: "rowhead" }, "저장소 \\ 인스턴스")];
  matrix.columns.forEach((col) => {
    const label = col.reachable ? col.name : `${col.name} ⚠`;
    headCells.push(el("th", { title: col.error || col.name }, label));
  });
  const thead = el("thead", {}, el("tr", {}, headCells));

  const body = rows.map((row) => {
    const tds = [
      el("td", { class: "rowhead" }, [
        el("span", { class: "link", title: "설정 자세히 비교", onclick: () => openRepoDiff(row.repository) }, row.repository),
        rowStatusBadge(row.status),
      ]),
    ];
    matrix.columns.forEach((col) => {
      const c = row.cells[col.id] || { present: false };
      let cls, mark, meta;
      if (c.unknown) { cls = "unknown"; mark = "?"; meta = ""; }
      else if (!c.present) { cls = "missing"; mark = "—"; meta = ""; }
      else if (c.matches_reference) { cls = "consistent"; mark = "✓"; meta = c.format || ""; }
      else { cls = "drift"; mark = "≠"; meta = [c.type, c.remote_url].filter(Boolean).join(" · ") || c.format || ""; }

      const inner = el("span", { class: `mcell ${cls}`, title: cellDetail(c) }, [
        el("span", { class: "mark" }, mark),
        meta ? el("span", { class: "meta" }, meta) : null,
      ]);
      tds.push(el("td", {}, inner));
    });
    return el("tr", {}, tds);
  });

  const table = el("table", { class: "matrix" }, [thead, el("tbody", {}, body)]);
  container.append(table);
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
  renderMatrix();
}

document.getElementById("drift-only").addEventListener("change", renderMatrix);

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
  refreshActiveTab();
}

init();
