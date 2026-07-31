// Standalone public "네트워크 Ping 상태" page (served at /ping) — no login.
// Reads the public /api/ping-history and renders the same per-node latency
// charts as the app's 네트워크 체크 탭, without the app shell or any auth.
(function () {
  "use strict";
  var state = { days: 1 };
  var SVGNS = "http://www.w3.org/2000/svg";

  function el(tag, props, children) {
    var n = document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (k) {
      if (k === "class") n.className = props[k];
      else n.setAttribute(k, props[k]);
    });
    (Array.isArray(children) ? children : children == null ? [] : [children]).forEach(function (c) {
      if (c == null) return;
      n.append(c.nodeType ? c : document.createTextNode(String(c)));
    });
    return n;
  }
  function svgEl(tag, props, text) {
    var n = document.createElementNS(SVGNS, tag);
    props = props || {};
    Object.keys(props).forEach(function (k) { n.setAttribute(k, props[k]); });
    if (text != null) n.textContent = text;
    return n;
  }
  function pingColor(c) {
    return c === "crit" ? "var(--red)" : c === "warn" ? "var(--amber)" : "var(--accent)";
  }
  async function api(path) {
    var res = await fetch(path, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function renderChart(s) {
    var unit = "ms";
    var wrap = el("div", { class: "infra-chart" });
    var headNote = s.baseline != null ? ("평소(중앙값) " + s.baseline + " " + unit)
      : (s.detail ? "측정 실패" : "데이터 없음");
    wrap.append(el("div", { class: "infra-chart-head" }, [
      el("span", { class: "infra-name" }, s.name),
      el("span", { class: "url" }, headNote),
    ]));
    if (!s.points.length) {
      wrap.append(el("div", { class: s.detail ? "empty site-error" : "empty" },
        s.detail || "측정 데이터가 아직 없습니다."));
      return wrap;
    }
    var W = 520, H = 200, padL = 44, padR = 10, padT = 12, padB = 26;
    var ts = s.points.map(function (p) { return p.t; });
    var tmin = Math.min.apply(null, ts), tmax = Math.max.apply(null, ts);
    var tspan = Math.max(tmax - tmin, 1);
    var vmax = (Math.max.apply(null, [s.baseline || 0].concat(s.points.map(function (p) { return p.v; }))) || 1) * 1.15;
    var xOf = function (t) { return padL + ((t - tmin) / tspan) * (W - padL - padR); };
    var yOf = function (v) { return H - padB - (v / vmax) * (H - padT - padB); };

    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, class: "infra-svg" });
    svg.append(svgEl("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, class: "axis" }));
    svg.append(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: H - padB, class: "axis" }));
    if (s.baseline != null) {
      var by = yOf(s.baseline);
      svg.append(svgEl("line", { x1: padL, y1: by, x2: W - padR, y2: by, class: "baseline" }));
    }
    var coords = s.points.map(function (p) { return { x: xOf(p.t), y: yOf(p.v), p: p }; });
    var d = coords.map(function (c, i) { return (i ? "L" : "M") + c.x.toFixed(1) + " " + c.y.toFixed(1); }).join(" ");
    svg.append(svgEl("path", { d: d, class: "infra-line", fill: "none" }));
    coords.forEach(function (c) {
      svg.append(svgEl("circle", { cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: c.p.color === "ok" ? 2.2 : 3.4, fill: pingColor(c.p.color) }));
    });
    var crosshair = svgEl("line", { x1: 0, y1: padT, x2: 0, y2: H - padB, class: "crosshair", style: "display:none" });
    var hi = svgEl("circle", { cx: 0, cy: 0, r: 5, class: "hi", style: "display:none" });
    svg.append(crosshair); svg.append(hi);
    svg.append(svgEl("text", { x: 4, y: padT + 8, class: "axis-label" }, Math.round(vmax) + unit));
    svg.append(svgEl("text", { x: padL, y: H - 8, class: "axis-label" }, new Date(tmin * 1000).toLocaleString()));
    svg.append(svgEl("text", { x: W - padR, y: H - 8, class: "axis-label", "text-anchor": "end" }, new Date(tmax * 1000).toLocaleString()));
    wrap.append(svg);

    var tip = el("div", { class: "infra-tip", style: "display:none" });
    wrap.append(tip);
    svg.addEventListener("mousemove", function (ev) {
      var rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      var vbX = ((ev.clientX - rect.left) / rect.width) * W;
      var best = coords[0], bd = Infinity;
      coords.forEach(function (c) { var dx = Math.abs(c.x - vbX); if (dx < bd) { bd = dx; best = c; } });
      crosshair.setAttribute("x1", best.x); crosshair.setAttribute("x2", best.x); crosshair.style.display = "";
      hi.setAttribute("cx", best.x); hi.setAttribute("cy", best.y);
      hi.setAttribute("stroke", pingColor(best.p.color)); hi.style.display = "";
      var dt = new Date(best.p.t * 1000);
      tip.textContent = best.p.v + " " + unit + " · 한국시간 " + dt.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
      tip.style.display = "block";
    });
    svg.addEventListener("mouseleave", function () {
      crosshair.style.display = "none"; hi.style.display = "none"; tip.style.display = "none";
    });
    return wrap;
  }

  async function load() {
    var container = document.getElementById("infra-charts");
    if (!container.firstChild) container.append(el("div", { class: "empty" }, "불러오는 중…"));
    var data;
    try { data = await api("/api/ping-history?days=" + (state.days || 1)); }
    catch (e) {
      container.innerHTML = "";
      container.append(el("div", { class: "empty" }, "조회 실패: " + e.message));
      return;
    }
    var wl = document.getElementById("infra-warn-label"), cl = document.getElementById("infra-crit-label");
    if (wl) wl.textContent = "+" + data.warn_pct + "% 이상";
    if (cl) cl.textContent = "+" + data.crit_pct + "% 이상";
    container.innerHTML = "";
    if (!data.series.length) {
      container.append(el("div", { class: "empty" }, "측정 데이터가 아직 없습니다. 잠시 후 다시 확인하세요. (백그라운드에서 누적 중)"));
      return;
    }
    var groups = new Map();
    data.series.forEach(function (s) {
      var g = (s.group || "").trim() || "(그룹 미지정)";
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(s);
    });
    var names = Array.from(groups.keys()).sort(function (a, b) { return a.localeCompare(b, "ko"); });
    var showHeads = names.length > 1 || (names.length === 1 && names[0] !== "(그룹 미지정)");
    var grid = el("div", { class: "infra-grid" });
    names.forEach(function (g) {
      if (showHeads) grid.append(el("div", { class: "infra-grouphead" }, g));
      groups.get(g).forEach(function (s) { grid.append(renderChart(s)); });
    });
    container.append(grid);
  }

  function setup() {
    document.querySelectorAll("#infra-range button").forEach(function (b) {
      b.addEventListener("click", function () {
        state.days = Number(b.dataset.days);
        document.querySelectorAll("#infra-range button").forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        load();
      });
    });
    var rb = document.getElementById("infra-refresh");
    if (rb) rb.addEventListener("click", load);
    var first = document.querySelector('#infra-range button[data-days="1"]');
    if (first) first.classList.add("active");
    load();
    setInterval(load, 30000);   // auto-refresh
  }

  if (document.readyState !== "loading") setup();
  else document.addEventListener("DOMContentLoaded", setup);
})();
