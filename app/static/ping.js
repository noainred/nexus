// Standalone public "네트워크 Ping 상태" page (served at /ping) — no login.
// Reads the public /api/ping-history and renders the same per-node latency
// charts as the app's 네트워크 체크 탭, without the app shell or any auth.
(function () {
  "use strict";
  var state = { days: 1, filter: "", data: null };
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
  // Time-axis separators per selected range: 1일=1시간, 7일=0.5일, 30일=7일,
  // 90일=14일, 365일=1개월. Ticks are aligned to natural boundaries (hour/day/
  // month) so the divisions line up with real clock/calendar marks.
  function timeTicks(days, tmin, tmax) {
    var ticks = [], d, t;
    if (days >= 365) {
      d = new Date(tmin * 1000); d.setDate(1); d.setHours(0, 0, 0, 0);
      while (d.getTime() / 1000 < tmin) d.setMonth(d.getMonth() + 1);
      while (d.getTime() / 1000 <= tmax) { ticks.push(d.getTime() / 1000); d.setMonth(d.getMonth() + 1); }
      return ticks;
    }
    var step = days <= 1 ? 3600 : days <= 7 ? 43200 : days <= 30 ? 604800 : 1209600;
    d = new Date(tmin * 1000);
    if (days <= 1) d.setMinutes(0, 0, 0); else d.setHours(0, 0, 0, 0);
    t = d.getTime() / 1000;
    while (t < tmin) t += step;
    for (; t <= tmax; t += step) ticks.push(t);
    return ticks;
  }
  function fmtTick(days, t) {
    var d = new Date(t * 1000);
    if (days <= 1) return d.getHours() + "시";
    if (days >= 365) return (d.getMonth() + 1) + "월";
    return (d.getMonth() + 1) + "/" + d.getDate();
  }
  async function api(path) {
    var res = await fetch(path, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function renderChart(s, days) {
    var unit = "ms";
    var wrap = el("div", { class: "infra-chart" });
    var headNote = s.baseline != null
      ? ("평소(중앙값) " + s.baseline + " · 평균 " + (s.mean != null ? s.mean : "-")
         + " · 최대 " + (s.peak != null ? s.peak : "-") + " " + unit)
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
    // Range separators (behind the data line). `days` comes from the response
    // the data belongs to — not state.days — so cached data from a previous
    // range is never drawn with the wrong tick spacing.
    days = days || state.days || 1;
    var ticks = timeTicks(days, tmin, tmax);
    var lstep = Math.max(1, Math.ceil(ticks.length / 8));
    ticks.forEach(function (tk, i) {
      if (tk <= tmin || tk >= tmax) return;
      var gx = xOf(tk).toFixed(1);
      svg.append(svgEl("line", { x1: gx, y1: padT, x2: gx, y2: H - padB, stroke: "rgba(148,170,197,0.16)", "stroke-width": "1", "stroke-dasharray": "2 4" }));
      if (i % lstep === 0) {
        svg.append(svgEl("text", { x: gx, y: H - padB + 13, class: "axis-label", "text-anchor": "middle" }, fmtTick(days, tk)));
      }
    });
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

  // Space-separated, case-insensitive OR filter on server names:
  // "WA NA" → charts whose name contains "WA" or "NA".
  function filterTerms() {
    return state.filter.trim().toLowerCase().split(/\s+/).filter(Boolean);
  }

  function render() {
    var container = document.getElementById("infra-charts");
    var data = state.data;
    if (!data) return;
    var wl = document.getElementById("infra-warn-label"), cl = document.getElementById("infra-crit-label");
    if (wl) wl.textContent = "+" + data.warn_pct + "% 이상";
    if (cl) cl.textContent = "+" + data.crit_pct + "% 이상";
    container.innerHTML = "";
    if (!data.series.length) {
      container.append(el("div", { class: "empty" }, "측정 데이터가 아직 없습니다. 잠시 후 다시 확인하세요. (백그라운드에서 누적 중)"));
      return;
    }
    var terms = filterTerms();
    var series = !terms.length ? data.series : data.series.filter(function (s) {
      var name = (s.name || "").toLowerCase();
      return terms.some(function (t) { return name.indexOf(t) !== -1; });
    });
    if (!series.length) {
      container.append(el("div", { class: "empty" }, "필터와 일치하는 서버가 없습니다."));
      return;
    }
    var grid = el("div", { class: "infra-grid" });
    if (terms.length) {
      // Filtered view: one flat grid, no group separation.
      series.forEach(function (s) { grid.append(renderChart(s, data.days)); });
    } else {
      var groups = new Map();
      series.forEach(function (s) {
        var g = (s.group || "").trim() || "(그룹 미지정)";
        if (!groups.has(g)) groups.set(g, []);
        groups.get(g).push(s);
      });
      var names = Array.from(groups.keys()).sort(function (a, b) { return a.localeCompare(b, "ko"); });
      var showHeads = names.length > 1 || (names.length === 1 && names[0] !== "(그룹 미지정)");
      names.forEach(function (g) {
        if (showHeads) grid.append(el("div", { class: "infra-grouphead" }, g));
        groups.get(g).forEach(function (s) { grid.append(renderChart(s, data.days)); });
      });
    }
    container.append(grid);
  }

  var loadSeq = 0;   // 범위 클릭/자동 갱신 경합 시 뒤늦은 이전 응답 폐기용
  async function load() {
    var container = document.getElementById("infra-charts");
    if (!container.firstChild) container.append(el("div", { class: "empty" }, "불러오는 중…"));
    var mySeq = ++loadSeq;
    var data;
    try { data = await api("/api/ping-history?days=" + (state.days || 1)); }
    catch (e) {
      if (mySeq !== loadSeq) return;   // 더 새 요청이 이미 나감 — 이 실패는 무시
      state.data = null;               // 실패 시 캐시 폐기 — 필터 입력이 죽은 데이터를 되살리지 않도록
      container.innerHTML = "";
      container.append(el("div", { class: "empty" }, "조회 실패: " + e.message));
      return;
    }
    if (mySeq !== loadSeq) return;     // 뒤늦게 도착한 이전 범위 응답 폐기
    state.data = data;
    render();
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
    var fi = document.getElementById("infra-filter");
    var filterTimer = null;
    if (fi) fi.addEventListener("input", function () {
      state.filter = fi.value;
      // 디바운스: 타이핑(특히 한글 IME 자모 단위 input)마다 전체 차트를
      // 파괴·재구축하지 않도록 잠깐 모아서 한 번만 다시 그린다. 재조회 없음.
      clearTimeout(filterTimer);
      filterTimer = setTimeout(render, 150);
    });
    var first = document.querySelector('#infra-range button[data-days="1"]');
    if (first) first.classList.add("active");
    load();
    setInterval(load, 30000);   // auto-refresh
  }

  if (document.readyState !== "loading") setup();
  else document.addEventListener("DOMContentLoaded", setup);
})();
