/* EE Rankings UI. Depends on rank.js (window.EERank). */
(function () {
  "use strict";

  var PAGE = 100;
  var data = null;
  var areaMeta = {}; // areaPos -> {id, name, venues, default}
  var defaultAreas = [];
  var state = { areas: new Set(), from: 0, to: 0, region: "world", dept: "eeplus", q: "" };
  var shown = PAGE;
  var openRows = new Set();
  var lastResults = [];

  var $ = function (sel) { return document.querySelector(sel); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function displayName(n) { return n.replace(/\s+\d{4}$/, ""); }
  function fmt(x) { return x >= 100 ? x.toFixed(0) : x.toFixed(1); }

  // ---------- URL state ----------
  function readHash() {
    var h = location.hash.replace(/^#/, "");
    if (h === "about") return "about";
    var params = new URLSearchParams(h);
    if (params.has("areas")) {
      var ids = params.get("areas") === "none" ? [] : params.get("areas").split(",");
      state.areas = new Set(ids.filter(function (id) { return data.areaIds.indexOf(id) >= 0; }));
    }
    if (params.has("from")) state.from = clampYear(+params.get("from"));
    if (params.has("to")) state.to = clampYear(+params.get("to"));
    if (state.from > state.to) { var t = state.from; state.from = state.to; state.to = t; }
    if (params.has("region")) state.region = params.get("region");
    if (params.has("dept")) state.dept = params.get("dept");
    return "rank";
  }
  function clampYear(y) { return Math.max(data.minYear, Math.min(data.maxYear, y || data.maxYear)); }
  function writeHash() {
    var p = new URLSearchParams();
    var isDefault = state.areas.size === defaultAreas.length && defaultAreas.every(function (id) { return state.areas.has(id); });
    if (!isDefault) p.set("areas", state.areas.size ? data.areaIds.filter(function (id) { return state.areas.has(id); }).join(",") : "none");
    p.set("from", state.from);
    p.set("to", state.to);
    if (state.region !== "world") p.set("region", state.region);
    if (state.dept !== "eeplus") p.set("dept", state.dept);
    history.replaceState(null, "", "#" + p.toString());
  }

  // ---------- Areas panel ----------
  function renderAreas() {
    var html = "";
    data.areas.groups.forEach(function (g, gi) {
      html += '<div class="group" data-group="' + esc(g.id) + '"><div class="group-head"><h3><span class="dot g' + gi + '"></span>' + esc(g.name) +
        '</h3><button data-group-toggle="' + esc(g.id) + '">Toggle</button></div>';
      g.areas.forEach(function (a) {
        html += '<label class="area' + (a["default"] ? "" : " adjacent") + '"><input type="checkbox" value="' + esc(a.id) + '"' +
          (state.areas.has(a.id) ? " checked" : "") + '><span>' + esc(a.name) +
          (a["default"] ? "" : ' <span class="adj-tag" title="EE-adjacent area, not selected by default">adjacent</span>') +
          '<span class="venues">' + esc(a.venues.join(" · ")) + "</span></span></label>";
      });
      html += "</div>";
    });
    $("#area-groups").innerHTML = html;
  }
  function syncAreaChecks() {
    document.querySelectorAll("#area-groups input").forEach(function (cb) { cb.checked = state.areas.has(cb.value); });
  }

  // ---------- Ranking table ----------
  function matchesSearch(r, q) {
    if (!q) return true;
    if (r.inst[0].toLowerCase().indexOf(q) >= 0) return true;
    for (var i = 0; i < r.faculty.length; i++) {
      if (r.faculty[i].author[0].toLowerCase().indexOf(q) >= 0) return true;
    }
    return false;
  }

  function instTotal(r) {
    var total = 0;
    for (var k in r.areaTotals) total += r.areaTotals[k];
    return total;
  }

  // Bar length is proportional to the institution's total adjusted count (relative to the largest
  // shown); segments are colored by area group.
  function miniBars(r, maxTotal) {
    var parts = [];
    var total = instTotal(r);
    if (!total || !maxTotal) return "";
    data.areaIds.forEach(function (id, pos) {
      var v = r.areaTotals[pos];
      if (!v) return;
      parts.push('<span class="g' + areaMeta[pos].group + '" title="' + esc(areaMeta[pos].name + ": " + fmt(v)) +
        '" style="flex:' + v.toFixed(3) + '"></span>');
    });
    var width = Math.max(2, 100 * total / maxTotal).toFixed(1);
    return '<div class="minibars" style="width:' + width + '%" aria-hidden="true">' + parts.join("") + "</div>";
  }

  function detailHtml(r) {
    var chips = Object.keys(r.areaTotals).map(Number).sort(function (a, b) { return r.areaTotals[b] - r.areaTotals[a]; })
      .map(function (pos) { return '<span class="chip">' + esc(areaMeta[pos].name) + " <b>" + fmt(r.areaTotals[pos]) + "</b></span>"; });
    var rows = r.faculty.map(function (f) {
      var a = f.author; // [name, instIdx, dept, pid, home, scholar, rows]
      var dblp = a[3] ? "https://dblp.org/pid/" + a[3] + ".html" : "https://dblp.org/search?q=" + encodeURIComponent(displayName(a[0]));
      var nameLink = '<a href="' + esc(a[4] || dblp) + '" target="_blank" rel="noopener">' + esc(displayName(a[0])) + "</a>";
      var links = '<span class="fac-links"><a href="' + esc(dblp) + '" target="_blank" rel="noopener" title="DBLP">dblp</a>' +
        (a[5] ? '<a href="' + esc(a[5]) + '" target="_blank" rel="noopener" title="Google Scholar">scholar</a>' : "") + "</span>";
      var deptLabel = { ee: "EE/ECE", other: "other dept", unknown: "dept n/a" }[a[2]] || a[2];
      var top = Object.keys(f.perArea).map(Number).sort(function (x, y) { return f.perArea[y][1] - f.perArea[x][1]; })
        .slice(0, 3).map(function (pos) { return esc(areaMeta[pos].name); }).join(", ");
      var badge = a[2] === "unknown" ? "" : '<span class="badge ' + esc(a[2]) + '">' + esc(deptLabel) + "</span>";
      return "<tr><td>" + nameLink + badge + links +
        '<div class="fac-areas">' + top + '</div></td><td class="num hide-sm">' + f.count + '</td><td class="num">' + fmt(f.adj) + "</td></tr>";
    });
    return '<tr class="detail"><td colspan="4"><div class="detail-inner"><div class="area-breakdown">' + chips.join("") +
      '</div><table class="fac-table"><thead><tr><th>Faculty</th><th class="num hide-sm">Papers</th><th class="num" title="Author-adjusted count">Adj.</th></tr></thead><tbody>' +
      rows.join("") + "</tbody></table></div></td></tr>";
  }

  function renderTable() {
    var q = state.q.trim().toLowerCase();
    var rows = lastResults.filter(function (r) { return matchesSearch(r, q); });
    var html = "";
    var maxTotal = 0;
    rows.forEach(function (r) { maxTotal = Math.max(maxTotal, instTotal(r)); });
    rows.slice(0, shown).forEach(function (r) {
      var open = openRows.has(r.idx);
      html += '<tr class="inst-row' + (open ? " open" : "") + '" data-idx="' + r.idx + '" tabindex="0" aria-expanded="' + open + '">' +
        '<td class="num">' + r.rank + "</td><td><div class=\"inst-name\"><span class=\"caret\">▸</span>" + esc(r.inst[0]) +
        ' <span class="country">' + esc(r.inst[1]) + "</span></div>" + miniBars(r, maxTotal) + "</td>" +
        '<td class="num">' + fmt(r.score) + '</td><td class="num">' + r.facultyCount + "</td></tr>";
      if (open) html += detailHtml(r);
    });
    if (!rows.length) {
      html = '<tr><td colspan="4" class="empty">' + (state.areas.size ? "No institutions match these filters." : "Select at least one area.") + "</td></tr>";
    }
    $("#ranking tbody").innerHTML = html;
    $("#more").hidden = rows.length <= shown;
    $("#more").textContent = "Show more (" + (rows.length - shown) + " remaining)";
    var isDefault = state.areas.size === defaultAreas.length && defaultAreas.every(function (id) { return state.areas.has(id); });
    var selectedNames = isDefault ? "core EE areas" : state.areas.size === data.areaIds.length ? "all areas" :
      state.areas.size + " of " + data.areaIds.length + " areas";
    $("#table-meta").textContent = rows.length + " institutions · " + selectedNames + " · " + state.from + "–" + state.to;
  }

  function recompute() {
    var ac = document.getElementById("area-count");
    if (ac) ac.textContent = "(" + state.areas.size + "/" + data.areaIds.length + ")";
    lastResults = window.EERank.computeRanking(data, state);
    renderTable();
    writeHash();
  }

  // ---------- About page ----------
  function renderVenueTable() {
    var html = "<table><thead><tr><th>Area</th><th>Venues</th></tr></thead><tbody>";
    data.areas.groups.forEach(function (g) {
      g.areas.forEach(function (a) {
        html += "<tr><td>" + esc(a.name) + "</td><td>" + esc(a.venues.join(", ")) + "</td></tr>";
      });
    });
    $("#venue-table").innerHTML = html + "</tbody></table>";
  }

  function showView(v) {
    $("#view-rank").hidden = v !== "rank";
    $("#view-about").hidden = v !== "about";
    document.querySelectorAll("nav a").forEach(function (a) { a.classList.toggle("active", a.dataset.view === v); });
  }

  // ---------- Wiring ----------
  function init(json) {
    data = json;
    var pos = 0;
    data.areas.groups.forEach(function (g, gi) { g.areas.forEach(function (a) { a.group = gi; areaMeta[pos++] = a; }); });
    defaultAreas = data.areaIds.filter(function (id, i) { return areaMeta[i]["default"] !== false; });
    state.areas = new Set(defaultAreas);
    state.to = data.maxYear;
    state.from = data.maxYear - 10;
    var view = readHash();

    var years = "";
    for (var y = data.maxYear; y >= data.minYear; y--) years += "<option>" + y + "</option>";
    $("#from").innerHTML = years;
    $("#to").innerHTML = years;
    $("#from").value = state.from;
    $("#to").value = state.to;
    $("#region").value = state.region;
    $("#dept").value = state.dept;
    $("#generated").textContent = "Data generated " + data.generated + " · " + data.authors.length.toLocaleString() + " faculty · " + data.institutions.length.toLocaleString() + " institutions";

    renderAreas();
    renderVenueTable();
    if (window.matchMedia("(max-width: 860px)").matches) $("#areas-details").removeAttribute("open");
    // On desktop the summary is a plain header; keep it from collapsing the panel.
    $("#areas-details > summary").addEventListener("click", function (e) {
      if (e.target.closest("button") || !window.matchMedia("(max-width: 860px)").matches) e.preventDefault();
    });
    showView(view);
    recompute();

    $("#area-groups").addEventListener("change", function (e) {
      if (e.target.type !== "checkbox") return;
      if (e.target.checked) state.areas.add(e.target.value); else state.areas.delete(e.target.value);
      shown = PAGE;
      recompute();
    });
    $("#area-groups").addEventListener("click", function (e) {
      var gid = e.target.dataset && e.target.dataset.groupToggle;
      if (!gid) return;
      var g = data.areas.groups.filter(function (x) { return x.id === gid; })[0];
      var allOn = g.areas.every(function (a) { return state.areas.has(a.id); });
      g.areas.forEach(function (a) { if (allOn) state.areas.delete(a.id); else state.areas.add(a.id); });
      syncAreaChecks();
      recompute();
    });
    document.querySelectorAll("[data-all]").forEach(function (b) {
      b.addEventListener("click", function () {
        var mode = b.dataset.all;
        state.areas = mode === "on" ? new Set(data.areaIds) : mode === "core" ? new Set(defaultAreas) : new Set();
        syncAreaChecks();
        recompute();
      });
    });
    ["from", "to", "region", "dept"].forEach(function (id) {
      $("#" + id).addEventListener("change", function (e) {
        state[id] = id === "from" || id === "to" ? +e.target.value : e.target.value;
        if (state.from > state.to) {
          if (id === "from") state.to = state.from; else state.from = state.to;
          $("#from").value = state.from;
          $("#to").value = state.to;
        }
        shown = PAGE;
        recompute();
      });
    });
    var searchTimer;
    $("#search").addEventListener("input", function (e) {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { state.q = e.target.value; shown = PAGE; renderTable(); }, 120);
    });
    function toggleRow(tr) {
      var idx = +tr.dataset.idx;
      if (openRows.has(idx)) openRows.delete(idx); else openRows.add(idx);
      renderTable();
    }
    $("#ranking tbody").addEventListener("click", function (e) {
      if (e.target.closest("a")) return;
      var tr = e.target.closest("tr.inst-row");
      if (tr) toggleRow(tr);
    });
    $("#ranking tbody").addEventListener("keydown", function (e) {
      var tr = e.target.closest && e.target.closest("tr.inst-row");
      if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleRow(tr); }
    });
    $("#more").addEventListener("click", function () { shown += PAGE; renderTable(); });
    document.querySelectorAll("nav a").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        if (a.dataset.view === "about") { history.pushState(null, "", "#about"); showView("about"); window.scrollTo(0, 0); }
        else { showView("rank"); writeHash(); }
      });
    });
    window.addEventListener("popstate", function () { showView(location.hash === "#about" ? "about" : "rank"); });
  }

  fetch("data/rankings.json")
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(init)
    .catch(function (err) {
      $("#table-meta").textContent = "Could not load data/rankings.json (" + err.message + "). Run `make data` and serve the site/ directory over HTTP.";
    });
})();
