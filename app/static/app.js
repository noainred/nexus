"use strict";

const state = {
  instances: [],
  current: null,
  componentToken: null,
  componentRepo: null,
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
  if (!state.current) return;
  let stores = [];
  try {
    stores = await api(`/api/instances/${state.current}/blobstores`);
  } catch (e) {
    container.append(el("div", { class: "empty" }, `Blob store 조회 실패: ${e.message}`));
    return;
  }
  if (!stores.length) {
    container.append(el("div", { class: "empty" }, "Blob store가 없습니다."));
    return;
  }
  const rows = stores.map((b) =>
    el("tr", {}, [
      el("td", {}, b.name),
      el("td", {}, b.type || "—"),
      el("td", {}, fmtBytes(b.total_size_bytes)),
      el("td", {}, fmtBytes(b.available_space_bytes)),
      el("td", {}, b.blob_count != null ? b.blob_count.toLocaleString() : "—"),
    ])
  );
  container.append(buildTable(["이름", "유형", "사용량", "가용 공간", "Blob 수"], rows));
}

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
      el("td", {}, el("button", { class: "danger", onclick: () => deleteRepo(r.name) }, "삭제")),
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
  refreshActiveTab();
}

init();
