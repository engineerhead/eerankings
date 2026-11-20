# EE Rankings

A metrics-based ranking of **electrical engineering** research institutions, modeled on
[CSrankings](https://csrankings.org). Institutions are ranked by how much their faculty publish in the most
selective venues of each EE area. Reputation surveys play no part.

## Methodology

* **Venues.** Each of the 17 areas (solid-state circuits, devices and photonics, design automation, signal
  processing, information theory, communications, control, power and energy, and others) has a small set of
  flagship venues, listed in [`data/areas.json`](data/areas.json). Machine learning, vision, robotics, and
  security are *EE-adjacent*. They are unselected by default, because CS dominates their venues.
  Workshops, companions, editorials, errata, and panel sessions are excluded.
* **Credit.** Every paper gives each author `1 / (number of authors)`.
* **Area count.** An institution's count in an area is the sum of that credit over its faculty, within the
  selected years.
* **Score.** The geometric mean of `(area count + 1)` over the selected areas. This rewards breadth, and no
  single area dominates.
* **Faculty.** Faculty are people whose current DBLP affiliation resolves to an academic institution. They
  must also have at least 7 years of publishing, at least 20 DBLP records, recent activity, and at least 3
  papers in counted venues. Departments are classified from the affiliation string as EE/ECE, other, or
  unspecified, and the UI can filter on this. [`data/faculty-overrides.csv`](data/faculty-overrides.csv)
  always wins over the heuristic.

## Layout

```
data/areas.json                  areas, groups, and DBLP venue keys
data/faculty-overrides.csv       curated include/exclude and affiliation fixes
data/institution-aliases.csv     spelling variants -> canonical institution
data/institutions.csv            optional country/region/homepage overrides
scripts/extract_dblp.py          phase 1: stream the DBLP dump (slow, ~5 min)
scripts/affil.py                 affiliation-string parser
scripts/build_site.py            phase 2: build site/data/rankings.json (fast)
site/                            static site (index.html, app.js, rank.js, style.css, data/)
tests/                           Python (affiliation parser) and Node (scoring) tests
```

## Building

Requirements: Python 3.9+ (standard library only), `curl`, and Node 18+ to run the JS tests.

```sh
make download   # fetch dblp.xml.gz (~1.1 GB) into raw/
make data       # extract + build site/data/rankings.json
make test       # unit tests
make serve      # http://localhost:8000
```

DBLP throttles each connection to roughly 10 KB/s after the first few hundred MB. If `make download` stalls,
finish the file with parallel range requests:
`scripts/fetch_parallel.sh https://dblp.org/xml/dblp.xml.gz raw/dblp.xml.gz <content-length> 16`.

`site/` is fully static. Deploy it to GitHub Pages, Netlify, S3, or any other static host. The generated
`site/data/rankings.json` is committed, so the site works without rebuilding.

## Corrections

* **Wrong or missing affiliation:** update it on DBLP or ORCID, or add a row to `data/faculty-overrides.csv`.
* **Duplicate institution names:** add a row to `data/institution-aliases.csv`.
* **New venue:** add its DBLP key prefix (for example `conf/isscc`) to `data/areas.json`, then run `make clean data`.

## Known limitations

* DBLP does not index several flagship EE venues, such as IEDM, CLEO, APEC, IMS, and the IEEE Antennas &
  Propagation symposium. Devices and photonics are represented by VLSI Technology and OFC, and power
  electronics by IEEE TIE. Electromagnetics is not covered.
* The faculty heuristic cannot distinguish faculty from long-term postdocs or research scientists. Curated
  overrides fix individual cases.

Publication data comes from [DBLP](https://dblp.org) (CC0).
