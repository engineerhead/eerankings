PY ?= python3
DBLP_URL = https://dblp.org/xml/dblp.xml.gz

.PHONY: all download extract data test serve clean

all: data

raw/dblp.xml.gz:
	mkdir -p raw
	curl -fSL -o $@ $(DBLP_URL)

download: raw/dblp.xml.gz

# Phase 1 (slow, ~5 min): stream the DBLP dump, keep tracked-venue papers, person pages, careers.
raw/pubs.jsonl: raw/dblp.xml.gz data/areas.json scripts/extract_dblp.py
	$(PY) scripts/extract_dblp.py raw/dblp.xml.gz data/areas.json raw

extract: raw/pubs.jsonl

# Phase 2 (fast): affiliations -> institutions, faculty selection, site/data/rankings.json.
data: raw/pubs.jsonl
	$(PY) scripts/build_site.py raw site/data/rankings.json

test:
	$(PY) -m unittest discover -s tests -p 'test_*.py'
	node --test tests/*.test.js

serve:
	cd site && $(PY) -m http.server 8000

clean:
	rm -f raw/pubs.jsonl raw/people.jsonl raw/careers.json raw/venue_counts.json
