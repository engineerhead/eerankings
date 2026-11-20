"""Parse DBLP affiliation strings into (institution, country, department class).

DBLP affiliations look like:
  "University of California, Berkeley, Department of EECS, CA, USA"
  "Stanford University, Department of Electrical Engineering, CA, USA"
  "ETH Zurich, Department of Information Technology and Electrical Engineering, Switzerland"
  "Tsinghua University, Beijing, China"
"""
import re

US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split()
)
CA_PROVINCES = set("AB BC MB NB NL NS NT NU ON PE QC SK YT".split())

COUNTRY_ALIASES = {
    "usa": "USA", "us": "USA", "united states": "USA", "united states of america": "USA",
    "uk": "UK", "united kingdom": "UK", "england": "UK", "scotland": "UK", "wales": "UK", "great britain": "UK",
    "pr china": "China", "p.r. china": "China", "peoples r china": "China", "people's republic of china": "China",
    "china": "China", "hong kong": "Hong Kong", "hong kong sar": "Hong Kong", "hong kong, china": "Hong Kong",
    "macau": "Macau", "macao": "Macau", "taiwan": "Taiwan", "roc": "Taiwan",
    "south korea": "South Korea", "korea": "South Korea", "republic of korea": "South Korea",
    "the netherlands": "Netherlands", "netherlands": "Netherlands", "holland": "Netherlands",
    "uae": "UAE", "united arab emirates": "UAE", "czechia": "Czech Republic", "czech republic": "Czech Republic",
    "russian federation": "Russia", "deutschland": "Germany", "brasil": "Brazil",
    "españa": "Spain", "italia": "Italy", "schweiz": "Switzerland", "suisse": "Switzerland", "österreich": "Austria", "türkiye": "Turkey", "turkiye": "Turkey",
}

REGIONS = {
    "northamerica": ["USA", "Canada"],
    "europe": ["UK", "Germany", "France", "Switzerland", "Netherlands", "Belgium", "Italy", "Spain", "Portugal",
               "Austria", "Sweden", "Norway", "Denmark", "Finland", "Iceland", "Ireland", "Poland", "Czech Republic",
               "Slovakia", "Hungary", "Romania", "Bulgaria", "Greece", "Cyprus", "Croatia", "Slovenia", "Serbia",
               "Estonia", "Latvia", "Lithuania", "Luxembourg", "Malta", "Russia", "Ukraine", "Turkey"],
    "asia": ["China", "Hong Kong", "Macau", "Taiwan", "Japan", "South Korea", "Singapore", "India", "Israel",
             "Saudi Arabia", "UAE", "Qatar", "Iran", "Pakistan", "Bangladesh", "Malaysia", "Thailand", "Vietnam",
             "Indonesia", "Philippines", "Sri Lanka", "Jordan", "Lebanon", "Kuwait", "Oman", "Nepal"],
    "australasia": ["Australia", "New Zealand"],
    "southamerica": ["Brazil", "Chile", "Argentina", "Mexico", "Colombia", "Peru", "Uruguay", "Venezuela", "Ecuador"],
    "africa": ["South Africa", "Egypt", "Nigeria", "Morocco", "Tunisia", "Algeria", "Kenya", "Ghana", "Ethiopia"],
}
COUNTRY_REGION = {c: r for r, cs in REGIONS.items() for c in cs}

ACADEMIC_RE = re.compile(
    r"universit|univ\.|institute of technology|inst\. of tech|polytechnic|politecnico|polytechnique|"
    r"\beth\b|\bepfl\b|kaist|postech|technion|hochschule|\bcollege\b|école|ecole|indian institute|"
    r"weizmann|\bkth\b|\bdtu\b|caltech|universidad|universidade|università|universität|technische|"
    r"\bmit\b|\btu [a-z]|kaust|\bnyu\b|\bucla\b|\bucsd\b|imperial college|skoltech|tech\b|"
    r"institute of science and technology|william (&|and) mary|\bunist\b|\bgist\b|\bdgist\b|"
    r"\biit\b|\biiit\b|\bnit\b|sorbonne|sciences po|centralesup|grenoble inp|\binsa\b|\btelecom paris",
    re.I,
)
NONACADEMIC_RE = re.compile(
    r"\b(inc|corp|corporation|ltd|llc|gmbh|co\.|company|labs?|laboratories|research center|"
    r"hospital|clinic|ministry|government|bank|foundation)\b|google|microsoft|amazon|meta\b|facebook|"
    r"\bibm\b|intel\b|nvidia|samsung|huawei|alibaba|tencent|baidu|qualcomm|apple\b|"
    r"academy of sciences|cnrs|inria|max planck|fraunhofer|riken|csiro|a\*star|national laboratory|"
    r"hospital|medical cent",
    re.I,
)
DEPT_RE = re.compile(
    r"\b(department|dept\.?|school|faculty|division|college of|institute for|institute of|program|"
    r"laboratory|lab|centre|center|group|chair|graduate school|unit)\b|^(ece|eecs|cs|ee)$",
    re.I,
)
EE_RE = re.compile(
    r"electrical|electronic|\bece\b|\beecs\b|\bee\b|\be\.e\.|electrotechn|elektrotechn|"
    r"information technology and electrical|microelectronic|integrated circuit|electronics|"
    r"signal processing|information engineering|communication engineering|telecommunication|"
    r"control engineering|automation|photonics|optoelectronic|systems engineering",
    re.I,
)
OTHER_DEPT_RE = re.compile(
    r"computer science|informatics|computing|mathemat|statistic|mechanical|physics|chemi|biolog|"
    r"aerospace|aeronaut|civil|industrial|operations research|economics|business|management|medicine|"
    r"medical|neuroscience|psycholog|linguistic|bioengineering|biomedical|materials|robotics institute|"
    r"data science|artificial intelligence|software|environment|ecolog|sport|librar|humanities|social|"
    r"education|\blaw\b|\barts?\b|music|agricultur|pharma|nursing|rehabilitation|geoscience|geograph|"
    r"psychiatry|radiology|surgery|public health|finance|accounting|marketing|philosophy|history|"
    r"earth|ocean|astronom|cognitive",
    re.I,
)

DEPT_PREFIX_RE = re.compile(
    r"(department|dept\.?|school of|faculty of|division|college of|laboratory|lab\b|centre|center|group|"
    r"chair|program|graduate school|institute for|institute of (?!technology)|key lab|state key)",
    re.I,
)

UC_CAMPUSES = {"berkeley", "los angeles", "san diego", "santa barbara", "irvine", "davis", "riverside",
               "santa cruz", "merced", "san francisco"}
SYSTEM_SPLITS = {
    "university of california": UC_CAMPUSES,
    "university of maryland": {"college park", "baltimore county"},
    "university of colorado": {"boulder", "denver", "colorado springs"},
    "university of massachusetts": {"amherst", "lowell", "boston", "dartmouth"},
    "university of illinois": {"urbana-champaign", "chicago", "urbana champaign", "urbana"},
    "university of nevada": {"reno", "las vegas"},
    "university of texas": {"austin", "dallas", "arlington", "san antonio", "el paso"},
    "state university of new york": {"buffalo", "stony brook", "binghamton", "albany"},
    "university of wisconsin": {"madison", "milwaukee"},
    "university of north carolina": {"chapel hill", "charlotte"},
    "university of minnesota": {"twin cities", "duluth"},
    "university of michigan": {"ann arbor", "dearborn"},
    "university of tennessee": {"knoxville"},
    "university of nebraska": {"lincoln"},
    "university of missouri": {"columbia", "kansas city"},
    "rutgers university": {"new brunswick", "newark", "piscataway"},
}
# Names that need the following city segment to identify a campus: "Indian Institute of Technology, Delhi"
CITY_SYSTEMS = {"indian institute of technology", "national institute of technology",
                "indian institute of information technology", "indian institute of science education and research"}
# A bare system name with no recognizable campus cannot be attributed to one institution.
AMBIGUOUS_SYSTEMS = {"university of california", "california state university", "state university of new york",
                     "university of texas", "university of massachusetts", "university of north carolina"}
CAMPUS_CANON = {"urbana": "Urbana-Champaign", "urbana champaign": "Urbana-Champaign"}
ACRONYM_SUFFIX_RE = re.compile(r"\s*\(([A-Za-z][A-Za-z0-9&.\-]*)\)\s*$")
HK_NAMES_RE = re.compile(r"hong kong|kowloon", re.I)
MACAU_NAMES_RE = re.compile(r"macau|macao", re.I)


def strip_acronym(name):
    """'Beijing University of Posts and Telecommunications (BUPT)' -> without the acronym.
    Keeps campus qualifiers such as '(Shenzhen)' (fewer than two capitals)."""
    m = ACRONYM_SUFFIX_RE.search(name)
    if m and sum(1 for ch in m.group(1) if ch.isupper()) >= 2:
        return name[: m.start()].strip()
    return name


def norm_key(name):
    """Normalized form used to merge spelling variants of the same institution."""
    s = strip_acronym(name).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\bthe\b|\bat\b|\bof\b|\bin\b", " ", s)
    s = re.sub(r"[^a-z0-9À-￿]+", " ", s)
    return " ".join(s.split())


def parse_country(segments):
    """Return (country, remaining_segments). Handles 'CA, USA' and 'Ontario, Canada'."""
    if not segments:
        return None, segments
    last = segments[-1].strip().rstrip(".")
    key = last.lower()
    country = COUNTRY_ALIASES.get(key)
    if country is None:
        country = last if last in COUNTRY_REGION else None
    if country is None and last.upper() in US_STATES and len(last) == 2:
        return "USA", segments[:-1]
    if country is None:
        return None, segments
    rest = segments[:-1]
    if rest and country == "USA" and rest[-1].strip() in US_STATES:
        rest = rest[:-1]
    if rest and country == "Canada" and rest[-1].strip() in CA_PROVINCES:
        rest = rest[:-1]
    return country, rest


def dept_class(dept_text):
    if not dept_text:
        return "unknown"
    if EE_RE.search(dept_text):
        return "ee"
    if OTHER_DEPT_RE.search(dept_text):
        return "other"
    return "unknown"


def parse_affiliation(aff):
    """Return dict(institution, country, dept, dept_text) or None if not an academic institution."""
    segs = [s.strip() for s in aff.split(",") if s.strip()]
    country, segs = parse_country(segs)
    if not segs:
        return None
    inst = None
    inst_idx = None
    for i, s in enumerate(segs):
        if ACADEMIC_RE.search(s) and not DEPT_PREFIX_RE.match(s):
            inst, inst_idx = s, i
            break
    if inst is None:
        return None
    # Glue multi-campus systems: "University of California, Berkeley"
    inst = strip_acronym(inst)
    sys_key = inst.lower()
    if sys_key in SYSTEM_SPLITS:
        for seg in segs[inst_idx + 1:]:
            campus = strip_acronym(seg.strip())
            low = campus.lower()
            if low in SYSTEM_SPLITS[sys_key]:
                inst = "%s, %s" % (inst, CAMPUS_CANON.get(low, campus))
                break
    elif sys_key in CITY_SYSTEMS and inst_idx + 1 < len(segs):
        nxt = segs[inst_idx + 1].strip()
        if not DEPT_RE.search(nxt):
            inst = "%s %s" % (inst, nxt)
    if inst.lower() in AMBIGUOUS_SYSTEMS:
        return None
    # Hong Kong and Macau institutions are often written as "..., Hong Kong, China".
    if country == "China" and HK_NAMES_RE.search(aff) and not re.search(r"shenzhen|guangzhou", inst, re.I):
        country = "Hong Kong"
    elif country == "China" and MACAU_NAMES_RE.search(inst):
        country = "Macau"
    if NONACADEMIC_RE.search(inst) and (not re.search(r"universit", inst, re.I) or re.search(r"hospital", inst, re.I)):
        return None
    dept_parts = [s for j, s in enumerate(segs) if j != inst_idx and DEPT_RE.search(s)]
    # Departments are sometimes written before the institution: "Dept. of EE, MIT"
    dept_text = "; ".join(dept_parts)
    return {
        "institution": inst,
        "country": country,
        "dept": dept_class(dept_text),
        "dept_text": dept_text,
    }
