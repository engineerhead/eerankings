/* Ranking logic for EE Rankings. Pure functions, usable in the browser and in Node tests.
 *
 * Methodology (mirrors CSrankings):
 *  - Each paper in a tracked venue gives each author 1/(number of authors) "adjusted" credit.
 *  - An institution's score in an area is the sum of its faculty's adjusted counts there.
 *  - The overall score is the geometric mean over the selected areas of (area score + 1), so breadth
 *    across areas is rewarded and no single area dominates.
 */
(function (root) {
  "use strict";

  function deptAllowed(dept, mode) {
    if (mode === "all") return true;
    if (mode === "ee") return dept === "ee";
    return dept !== "other"; // "eeplus": EE/ECE + department unknown
  }

  function regionAllowed(inst, region) {
    // inst = [name, country, region, homepage]
    // region is "world", a region id ("europe"), or "c:<Country>" for a single country.
    if (!region || region === "world") return true;
    if (region.slice(0, 2) === "c:") return inst[1] === region.slice(2);
    if (region === "usa") return inst[1] === "USA"; // legacy links
    if (region === "canada") return inst[1] === "Canada";
    return inst[2] === region;
  }

  /**
   * @param data   parsed rankings.json
   * @param opts   {areas: Set<string>, from: number, to: number, region: string, dept: string}
   * @returns array of {inst, idx, score, facultyCount, areaTotals: {areaId: adj}, faculty: [...]},
   *          sorted by score descending, each with `rank` (ties share a rank).
   */
  function computeRanking(data, opts) {
    var areaIds = data.areaIds;
    var selected = [];
    for (var i = 0; i < areaIds.length; i++) if (opts.areas.has(areaIds[i])) selected.push(i);
    var selectedSet = {};
    selected.forEach(function (i) { selectedSet[i] = true; });

    var byInst = {};
    for (var a = 0; a < data.authors.length; a++) {
      var au = data.authors[a];
      // [name, instIdx, dept, pid, home, scholar, rows]
      var inst = data.institutions[au[1]];
      if (!regionAllowed(inst, opts.region) || !deptAllowed(au[2], opts.dept)) continue;
      var rows = au[6];
      var perArea = {};
      var adjTotal = 0, cntTotal = 0;
      for (var r = 0; r < rows.length; r++) {
        var row = rows[r]; // [areaPos, year, count, adj]
        if (!selectedSet[row[0]] || row[1] < opts.from || row[1] > opts.to) continue;
        var cell = perArea[row[0]] || (perArea[row[0]] = [0, 0]);
        cell[0] += row[2];
        cell[1] += row[3];
        adjTotal += row[3];
        cntTotal += row[2];
      }
      if (adjTotal <= 0) continue;
      var entry = byInst[au[1]];
      if (!entry) {
        entry = byInst[au[1]] = { idx: au[1], inst: inst, areaTotals: {}, faculty: [] };
      }
      for (var k in perArea) {
        entry.areaTotals[k] = (entry.areaTotals[k] || 0) + perArea[k][1];
      }
      entry.faculty.push({ author: au, adj: adjTotal, count: cntTotal, perArea: perArea });
    }

    var results = [];
    for (var key in byInst) {
      var e = byInst[key];
      var logSum = 0;
      for (var s = 0; s < selected.length; s++) {
        logSum += Math.log((e.areaTotals[selected[s]] || 0) + 1);
      }
      e.score = selected.length ? Math.exp(logSum / selected.length) : 0;
      e.facultyCount = e.faculty.length;
      e.faculty.sort(function (x, y) { return y.adj - x.adj; });
      results.push(e);
    }
    results.sort(function (x, y) {
      return y.score - x.score || y.facultyCount - x.facultyCount || (x.inst[0] < y.inst[0] ? -1 : 1);
    });
    var prevScore = null, prevRank = 0;
    for (var n = 0; n < results.length; n++) {
      var sc = Math.round(results[n].score * 10) / 10; // ties at displayed precision
      results[n].rank = sc === prevScore ? prevRank : n + 1;
      prevScore = sc;
      prevRank = results[n].rank;
    }
    return results;
  }

  var api = { computeRanking: computeRanking, deptAllowed: deptAllowed, regionAllowed: regionAllowed };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.EERank = api;
})(this);
