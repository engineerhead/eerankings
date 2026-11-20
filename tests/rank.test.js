// Run with: node --test tests/
const test = require("node:test");
const assert = require("node:assert");
const { computeRanking } = require("../site/rank.js");

const data = {
  areaIds: ["ssc", "sp"],
  institutions: [["Alpha U", "USA", "northamerica", ""], ["Beta U", "Germany", "europe", ""], ["Gamma U", "USA", "northamerica", ""]],
  authors: [
    // [name, instIdx, dept, pid, home, scholar, rows: [areaPos, year, count, adj]]
    ["A1", 0, "ee", null, null, null, [[0, 2020, 2, 1.0], [1, 2021, 1, 0.5]]],
    ["A2", 0, "other", null, null, null, [[1, 2022, 4, 3.0]]],
    ["B1", 1, "ee", null, null, null, [[0, 2020, 4, 3.0]]],
    ["C1", 2, "unknown", null, null, null, [[0, 2010, 9, 9.0]]],
  ],
};
const opts = (o) => Object.assign({ areas: new Set(["ssc", "sp"]), from: 2016, to: 2026, region: "world", dept: "eeplus" }, o);

test("geometric mean over selected areas", () => {
  const r = computeRanking(data, opts());
  // Alpha (eeplus excludes A2): ssc 1.0, sp 0.5 -> sqrt(2*1.5); Beta: ssc 3 -> sqrt(4*1) = 2
  assert.deepStrictEqual(r.map((x) => x.inst[0]), ["Beta U", "Alpha U"]);
  assert.ok(Math.abs(r[0].score - 2) < 1e-9);
  assert.ok(Math.abs(r[1].score - Math.sqrt(3)) < 1e-9);
});

test("year window excludes old papers", () => {
  const r = computeRanking(data, opts({ from: 2000 }));
  assert.strictEqual(r[0].inst[0], "Gamma U"); // sqrt(10*1)
});

test("department and region filters", () => {
  const all = computeRanking(data, opts({ dept: "all" }));
  const alpha = all.find((x) => x.inst[0] === "Alpha U");
  assert.strictEqual(alpha.facultyCount, 2);
  assert.ok(Math.abs(alpha.areaTotals[1] - 3.5) < 1e-9);
  const eu = computeRanking(data, opts({ region: "europe" }));
  assert.deepStrictEqual(eu.map((x) => x.inst[0]), ["Beta U"]);
  const us = computeRanking(data, opts({ region: "usa", from: 2000, dept: "ee" }));
  assert.deepStrictEqual(us.map((x) => x.inst[0]), ["Alpha U"]);
});

test("ties share a rank", () => {
  const d = { areaIds: ["x"], institutions: [["P", "USA", "northamerica", ""], ["Q", "USA", "northamerica", ""]],
    authors: [["p", 0, "ee", null, null, null, [[0, 2020, 1, 1]]], ["q", 1, "ee", null, null, null, [[0, 2020, 1, 1]]]] };
  const r = computeRanking(d, { areas: new Set(["x"]), from: 2016, to: 2026, region: "world", dept: "ee" });
  assert.deepStrictEqual(r.map((x) => x.rank), [1, 1]);
});

test("no areas selected yields zero scores", () => {
  const r = computeRanking(data, opts({ areas: new Set() }));
  assert.strictEqual(r.length, 0);
});
