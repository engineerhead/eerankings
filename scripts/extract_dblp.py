#!/usr/bin/env python3
"""Phase 1: stream the DBLP XML dump and extract what EE Rankings needs.

Outputs (in raw/):
  pubs.jsonl        one line per paper in a tracked venue:
                    {"k": key, "v": venue prefix, "y": year, "a": [authors], "t": title}
  people.jsonl      one line per DBLP person page with an affiliation or alias:
                    {"n": primary name, "al": [aliases], "aff": [affiliations], "url": [...]}
  careers.json      {author: [first_year, last_year, n_pubs]} for every author that
                    appears in a tracked-venue paper (used for the faculty heuristic)

Usage: python3 scripts/extract_dblp.py raw/dblp.xml.gz data/areas.json raw/
"""
import gzip
import html.entities
import json
import os
import re
import sys
import time

RECORD_TAGS = "article|inproceedings|proceedings|book|incollection|phdthesis|mastersthesis|www|data"
START_RE = re.compile(r'<(%s)\s[^>]*key="([^"]+)"' % RECORD_TAGS)
SPLIT_RE = re.compile(r"(</(?:%s)>)(?=<)" % RECORD_TAGS)
END_RE = re.compile(r"</(%s)>" % RECORD_TAGS)
AUTHOR_RE = re.compile(r"<author[^>]*>(.*?)</author>")
YEAR_RE = re.compile(r"<year>(\d{4})</year>")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S)
BOOKTITLE_RE = re.compile(r"<booktitle>(.*?)</booktitle>")
AFF_RE = re.compile(r'<note([^>]*)type="affiliation"([^>]*)>(.*?)</note>')
URL_RE = re.compile(r"<url[^>]*>(.*?)</url>")
TAG_RE = re.compile(r"<[^>]+>")
ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")
NUMREF_RE = re.compile(r"&#(x?[0-9A-Fa-f]+);")

XML_ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}


def unescape(s):
    """Resolve DBLP's ISO-Latin named entities, numeric refs, and XML escapes."""

    def named(m):
        name = m.group(1)
        if name in XML_ENTITIES:
            return XML_ENTITIES[name]
        cp = html.entities.name2codepoint.get(name)
        return chr(cp) if cp is not None else m.group(0)

    def numeric(m):
        v = m.group(1)
        try:
            return chr(int(v[1:], 16) if v[0] in "xX" else int(v))
        except ValueError:
            return m.group(0)

    return NUMREF_RE.sub(numeric, ENTITY_RE.sub(named, s))


def clean_text(s):
    return " ".join(unescape(TAG_RE.sub("", s)).split())


def load_venues(areas_path):
    with open(areas_path) as f:
        cfg = json.load(f)
    prefixes = []
    for g in cfg["groups"]:
        for a in g["areas"]:
            for v in a["venues"]:
                prefixes.extend(v["dblp"])
    return cfg, tuple(p + "/" for p in prefixes)


def iter_records(path):
    """Yield (tag, key, text) for every record in the dump."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="latin-1") as f:
        cur_tag = cur_key = None
        buf = []
        for raw_line in f:
            for line in SPLIT_RE.sub(r"\1\n", raw_line).split("\n"):
                if not line:
                    continue
                if cur_tag is None:
                    m = START_RE.search(line)
                    if not m:
                        continue
                    cur_tag, cur_key = m.group(1), m.group(2)
                    buf = [line]
                else:
                    buf.append(line)
                if END_RE.search(line) and ("</%s>" % cur_tag) in line:
                    yield cur_tag, cur_key, "\n".join(buf)
                    cur_tag = cur_key = None
                    buf = []


def main():
    dump, areas_path, outdir = sys.argv[1:4]
    cfg, prefixes = load_venues(areas_path)
    excl_book = re.compile(cfg["exclude_booktitle"])
    excl_title = re.compile(cfg["exclude_title"])

    # Pass over everything once; career stats are kept for all authors because we
    # don't yet know which ones will show up in tracked venues.
    first, last, count = {}, {}, {}
    venue_counts = {}
    all_counts = {}  # every venue prefix since 2016, to help discover keys for new areas
    n_pubs = n_people = 0
    t0 = time.time()
    pubs_f = open(os.path.join(outdir, "pubs.jsonl"), "w")
    people_f = open(os.path.join(outdir, "people.jsonl"), "w")
    for i, (tag, key, text) in enumerate(iter_records(dump)):
        if i % 500000 == 0 and i:
            print("  %d records, %.0fs" % (i, time.time() - t0), file=sys.stderr, flush=True)
        if tag == "www":
            if not key.startswith("homepages/"):
                continue
            names = [clean_text(a) for a in AUTHOR_RE.findall(text)]
            if not names:
                continue
            affs = []
            for pre, post, val in AFF_RE.findall(text):
                attrs = pre + post
                label = re.search(r'label="([^"]*)"', attrs)
                affs.append({"a": clean_text(val), "l": label.group(1) if label else ""})
            urls = [clean_text(u) for u in URL_RE.findall(text)]
            if affs or len(names) > 1:
                people_f.write(json.dumps({"n": names[0], "al": names[1:], "aff": affs, "url": urls, "k": key}, ensure_ascii=False) + "\n")
                n_people += 1
            continue

        authors = AUTHOR_RE.findall(text)
        if not authors:
            continue
        ym = YEAR_RE.search(text)
        year = int(ym.group(1)) if ym else 0
        authors = [clean_text(a) for a in authors]
        for a in authors:
            c = count.get(a)
            if c is None:
                count[a] = 1
                first[a] = year
                last[a] = year
            else:
                count[a] = c + 1
                if year and year < first[a]:
                    first[a] = year
                if year > last[a]:
                    last[a] = year

        prefix = key.rsplit("/", 1)[0]
        if tag in ("article", "inproceedings") and year >= 2016:
            all_counts[prefix] = all_counts.get(prefix, 0) + 1
        if tag not in ("article", "inproceedings") or not key.startswith(prefixes):
            continue
        bm = BOOKTITLE_RE.search(text)
        if bm and excl_book.search(clean_text(bm.group(1))):
            continue
        tm = TITLE_RE.search(text)
        title = clean_text(tm.group(1)) if tm else ""
        if excl_title.search(title):
            continue
        pubs_f.write(json.dumps({"k": key, "v": prefix, "y": year, "a": authors, "t": title}, ensure_ascii=False) + "\n")
        venue_counts[prefix] = venue_counts.get(prefix, 0) + 1
        n_pubs += 1

    pubs_f.close()
    people_f.close()

    # Only keep career stats for authors who appear in tracked venues or have a person page.
    wanted = set()
    with open(os.path.join(outdir, "pubs.jsonl")) as f:
        for line in f:
            wanted.update(json.loads(line)["a"])
    with open(os.path.join(outdir, "people.jsonl")) as f:
        for line in f:
            p = json.loads(line)
            wanted.add(p["n"])
            wanted.update(p["al"])
    careers = {a: [first[a], last[a], count[a]] for a in wanted if a in count}
    with open(os.path.join(outdir, "careers.json"), "w") as f:
        json.dump(careers, f, ensure_ascii=False)
    with open(os.path.join(outdir, "venue_counts.json"), "w") as f:
        json.dump(dict(sorted(venue_counts.items())), f, indent=1)
    with open(os.path.join(outdir, "all_venue_counts.json"), "w") as f:
        json.dump(dict(sorted(all_counts.items(), key=lambda kv: -kv[1])), f, indent=0)
    print("done: %d tracked papers, %d person pages, %d careers, %.0fs"
          % (n_pubs, n_people, len(careers), time.time() - t0), file=sys.stderr)


if __name__ == "__main__":
    main()
