#!/usr/bin/env python3
"""Phase 2: turn extracted DBLP data + curated files into site/data/rankings.json.

Usage: python3 scripts/build_site.py [raw_dir] [out_file]
"""
import collections
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from affil import COUNTRY_REGION, norm_key, parse_affiliation  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
MIN_YEAR = 2000

# Heuristic for "is this person plausibly a faculty member?" applied to DBLP-derived people.
# Curated entries in data/faculty-overrides.csv always win.
MIN_CAREER_YEARS = 7      # first DBLP publication at least this many years ago
MIN_TOTAL_PUBS = 20       # at least this many DBLP records overall
MIN_RECENT_YEAR_GAP = 3   # must have published something in the last few years
MIN_TRACKED_PUBS = 3      # at least this many papers in tracked EE venues


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if not (r.get(list(r.keys())[0]) or "").startswith("#")]


def load_areas():
    with open(os.path.join(ROOT, "data", "areas.json")) as f:
        cfg = json.load(f)
    prefix_area = {}
    prefix_venue = {}
    for g in cfg["groups"]:
        for a in g["areas"]:
            for v in a["venues"]:
                for p in v["dblp"]:
                    prefix_area[p] = a["id"]
                    prefix_venue[p] = v["name"]
    return cfg, prefix_area, prefix_venue


def current_affiliation(affs):
    for a in affs:
        # Labels such as "former", "PhD 2016", "until 2020" mark non-current affiliations.
        if not re.search(r"former|phd|ph\.d|doctor|until|previous|past|visiting|alumni|student|postdoc", a.get("l", ""), re.I):
            return a["a"]
    return None


def pick_urls(urls):
    home = orcid = scholar = None
    for u in urls:
        if "orcid.org" in u:
            orcid = orcid or u
        elif "scholar.google" in u:
            scholar = scholar or u
        elif u.startswith("http") and not re.search(r"dblp|wikipedia|wikidata|twitter|x\.com|linkedin|"
                                                     r"researchgate|github|mathgenealogy|acm\.org|ieee\.org|"
                                                     r"semanticscholar|zbmath|viaf|isni|loc\.gov|d-nb", u):
            home = home or u
    return home, orcid, scholar


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "raw")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "site", "data", "rankings.json")
    this_year = datetime.date.today().year
    cfg, prefix_area, prefix_venue = load_areas()

    # --- people & aliases -------------------------------------------------------------
    alias = {}
    people = {}
    with open(os.path.join(raw, "people.jsonl"), encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            people[p["n"]] = p
            for a in p["al"]:
                alias[a] = p["n"]

    def primary(name):
        return alias.get(name, name)

    # --- publications ---------------------------------------------------------------
    # pubs[author][area][year] = [count, adjusted]
    pubs = collections.defaultdict(lambda: collections.defaultdict(dict))
    venue_tally = collections.Counter()
    with open(os.path.join(raw, "pubs.jsonl"), encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            y = p["y"]
            if y < MIN_YEAR or y > this_year:
                continue
            area = prefix_area.get(p["v"])
            if not area:
                continue
            authors = list(dict.fromkeys(primary(a) for a in p["a"]))
            share = 1.0 / len(authors)
            venue_tally[p["v"]] += 1
            for a in authors:
                cell = pubs[a][area].get(y)
                if cell is None:
                    pubs[a][area][y] = [1, share]
                else:
                    cell[0] += 1
                    cell[1] += share

    # --- careers (merged over aliases) -------------------------------------------------
    with open(os.path.join(raw, "careers.json"), encoding="utf-8") as f:
        careers_raw = json.load(f)
    careers = {}
    for name, (fy, ly, n) in careers_raw.items():
        pn = primary(name)
        c = careers.get(pn)
        if c is None:
            careers[pn] = [fy or 9999, ly, n]
        else:
            c[0] = min(c[0], fy or 9999)
            c[1] = max(c[1], ly)
            c[2] += n

    # --- curated data --------------------------------------------------------------------
    inst_alias = {}
    for r in read_csv(os.path.join(ROOT, "data", "institution-aliases.csv")):
        inst_alias[norm_key(r["variant"])] = r["canonical"].strip()
    inst_meta = {}
    for r in read_csv(os.path.join(ROOT, "data", "institutions.csv")):
        inst_meta[norm_key(r["institution"])] = r
    overrides = {r["name"].strip(): r for r in read_csv(os.path.join(ROOT, "data", "faculty-overrides.csv"))}

    # --- select faculty -------------------------------------------------------------------
    name_countries = collections.defaultdict(collections.Counter)
    faculty = []
    stats = collections.Counter()
    candidates = set(pubs.keys()) | set(overrides.keys())
    for name in candidates:
        ov = overrides.get(name)
        if ov and ov.get("action", "").strip() == "exclude":
            stats["excluded_by_override"] += 1
            continue
        person = people.get(name)
        if ov and ov.get("affiliation"):
            aff_str = ov["affiliation"]
            parsed = parse_affiliation(aff_str) or {"institution": aff_str.split(",")[0].strip(),
                                                    "country": ov.get("country") or None,
                                                    "dept": "unknown", "dept_text": ""}
        else:
            if not person:
                stats["no_person_page"] += 1
                continue
            aff_str = current_affiliation(person["aff"])
            if not aff_str:
                stats["no_current_affiliation"] += 1
                continue
            parsed = parse_affiliation(aff_str)
            if not parsed:
                stats["non_academic"] += 1
                continue
        if ov and ov.get("dept"):
            parsed["dept"] = ov["dept"].strip()
        if ov and ov.get("country"):
            parsed["country"] = ov["country"].strip()

        if not ov:
            fy, ly, n = careers.get(name, [9999, 0, 0])
            tracked = sum(c[0] for ys in pubs[name].values() for c in ys.values())
            if fy > this_year - MIN_CAREER_YEARS:
                stats["career_too_short"] += 1
                continue
            if n < MIN_TOTAL_PUBS:
                stats["too_few_pubs"] += 1
                continue
            if ly < this_year - MIN_RECENT_YEAR_GAP:
                stats["inactive"] += 1
                continue
            if tracked < MIN_TRACKED_PUBS:
                stats["too_few_tracked"] += 1
                continue
        canon = inst_alias.get(norm_key(parsed["institution"]), parsed["institution"])
        name_key = norm_key(canon)
        if parsed["country"]:
            name_countries[name_key][parsed["country"]] += 1
        home, orcid, scholar = pick_urls(person["url"] if person else [])
        if ov and ov.get("homepage"):
            home = ov["homepage"]
        pid = person["k"].split("/", 1)[1] if person else None
        faculty.append({"name": name, "name_key": name_key, "display": canon, "country": parsed["country"],
                        "dept": parsed["dept"], "pid": pid, "home": home, "scholar": scholar})
        stats["faculty"] += 1

    # --- institutions ---------------------------------------------------------------------
    # Key on (name, country) so same-named universities in different countries stay separate
    # (e.g. Northeastern University in Boston vs. Shenyang). Affiliations without a country take the
    # dominant country for that name.
    inst_variants = collections.defaultdict(collections.Counter)
    for fac in faculty:
        meta = inst_meta.get(fac["name_key"], {})
        country = meta.get("country") or fac["country"]
        if not country and name_countries[fac["name_key"]]:
            country = name_countries[fac["name_key"]].most_common(1)[0][0]
        fac["inst"] = (fac["name_key"], country or "")
        inst_variants[fac["inst"]][fac["display"]] += 1
    inst_list = []
    inst_index = {}
    for key, variants in sorted(inst_variants.items()):
        meta = inst_meta.get(key[0], {})
        display = meta.get("institution") or variants.most_common(1)[0][0]
        country = key[1]
        region = meta.get("region") or COUNTRY_REGION.get(country, "other")
        inst_index[key] = len(inst_list)
        inst_list.append([display, country, region, meta.get("homepage", "")])

    # --- authors output ---------------------------------------------------------------------
    area_ids = [a["id"] for g in cfg["groups"] for a in g["areas"]]
    area_pos = {a: i for i, a in enumerate(area_ids)}
    authors_out = []
    for fac in sorted(faculty, key=lambda x: x["name"]):
        rows = []
        for area, ys in pubs.get(fac["name"], {}).items():
            for y, (c, adj) in ys.items():
                rows.append([area_pos[area], y, c, round(adj, 4)])
        if not rows and not overrides.get(fac["name"]):
            continue
        rows.sort()
        authors_out.append([fac["name"], inst_index[fac["inst"]], fac["dept"], fac["pid"], fac["home"],
                            fac["scholar"], rows])

    areas_out = {
        "groups": [{"id": g["id"], "name": g["name"],
                    "areas": [{"id": a["id"], "name": a["name"], "default": a.get("default", True),
                               "venues": [v["name"] for v in a["venues"]]}
                              for a in g["areas"]]} for g in cfg["groups"]]
    }
    data = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "minYear": MIN_YEAR,
        "maxYear": this_year,
        "areas": areas_out,
        "areaIds": area_ids,
        "institutions": inst_list,
        "authors": authors_out,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("faculty kept: %d, institutions: %d, size: %.1f MB" %
          (len(authors_out), len(inst_list), os.path.getsize(out) / 1e6), file=sys.stderr)
    print("selection stats:", dict(stats), file=sys.stderr)
    missing = [p for p in prefix_area if venue_tally[p] == 0]
    if missing:
        print("WARNING: venues with no papers since %d: %s" % (MIN_YEAR, ", ".join(missing)), file=sys.stderr)


if __name__ == "__main__":
    main()
