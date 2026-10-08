import html
import logging
import re
import time

import requests

import requests

from . import config
from .models import Job

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; jobbot/1.0; personal job search)"}
TIMEOUT = 30
US_STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)
LOCAL_MARKERS = ("greenville", "spartanburg", "south carolina", "greer", "simpsonville", "mauldin", "anderson, sc")
STOP_WORDS = {"senior", "junior", "sr", "jr", "lead", "principal", "staff", "ii", "iii", "i", "of", "the", "and", "a"}


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def is_remote(text: str) -> bool:
    return "remote" in (text or "").lower()


def is_local(location: str) -> bool:
    loc = (location or "").lower()
    return any(m in loc for m in LOCAL_MARKERS) or bool(re.search(r",\s*sc\b", loc))


def looks_us(location: str) -> bool:
    loc = (location or "").lower()
    if any(k in loc for k in ("united states", "usa", "u.s.", "north america", "americas")):
        return True
    if re.search(r"\bus\b", loc):
        return True
    return any(code in US_STATES for code in re.findall(r"\b[A-Z]{2}\b", location or ""))


def _wanted(remote: bool, location: str, country_ok: bool) -> bool:
    """Keep only jobs I could actually take: US-eligible remote, or in the local SC area."""
    return (remote and country_ok) or is_local(location)


def _title_keywords() -> list[set[str]]:
    """One normalized word-set per target title (stop words removed)."""
    sets = []
    for t in config.TARGET_TITLES:
        words = {_norm(w) for w in re.findall(r"[a-z0-9+#]+", t.lower()) if w not in STOP_WORDS and len(w) > 2}
        if words:
            sets.append(words)
    return sets


def _norm(w: str) -> str:
    return "administrator" if w in ("admin", "administrators", "administration", "sysadmin") else w


def _title_matches(title: str, keyword_sets: list[set[str]]) -> bool:
    if not keyword_sets:
        return True
    toks = {_norm(w) for w in re.findall(r"[a-z0-9+#]+", title.lower())}
    if "sysadmin" in title.lower():
        toks |= {"systems", "administrator"}
    return any(ks <= toks for ks in keyword_sets)


def _queries(queries: list[str]) -> list[str]:
    return list(dict.fromkeys(queries))[:4]


# --- Company career sites -------------------------------------------------

def _workday_us_facet(base: str) -> dict:
    """Finds the country facet id for the United States so the search is filtered server-side."""
    try:
        r = requests.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()

        def walk(facets):
            for f in facets:
                for v in f.get("values", []):
                    if v.get("descriptor") == "United States of America" and f.get("facetParameter"):
                        return {f["facetParameter"]: [v["id"]]}
                    if "facetParameter" in v:
                        hit = walk([v])
                        if hit:
                            return hit
            return None

        return walk(r.json().get("facets", [])) or {}
    except Exception as e:
        logging.warning("Workday facet lookup failed: %s", e)
        return {}


def workday(queries: list[str]) -> list[Job]:
    """Workday career sites (Red Hat, ...). Config entries look like 'company|host|site'."""
    jobs = []
    for entry in config.WORKDAY_SITES:
        try:
            company, host, site = [p.strip() for p in entry.split("|")]
        except ValueError:
            logging.warning("Bad WORKDAY_SITES entry: %r", entry)
            continue
        tenant = host.split(".")[0]
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        us_facet = _workday_us_facet(base)
        seen_paths = set()
        for q in _queries(queries):
            try:
                r = requests.post(
                    f"{base}/jobs", headers=HEADERS, timeout=TIMEOUT,
                    json={"appliedFacets": us_facet, "limit": 20, "offset": 0, "searchText": q},
                )
                r.raise_for_status()
                postings = r.json().get("jobPostings", [])
            except Exception as e:
                logging.warning("Workday %s failed for %r: %s", company, q, e)
                continue
            for p in postings:
                path = p.get("externalPath")
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                try:
                    d = requests.get(f"{base}{path}", headers=HEADERS, timeout=TIMEOUT)
                    d.raise_for_status()
                    info = d.json().get("jobPostingInfo", {})
                except Exception as e:
                    logging.warning("Workday detail failed %s: %s", path, e)
                    continue
                country = (info.get("country") or {}).get("descriptor", "")
                location = info.get("location") or p.get("locationsText", "")
                remote = (info.get("remoteType") or p.get("remoteType") or "").lower() == "remote" or is_remote(location)
                if not _wanted(remote, location, country.startswith("United States")):
                    continue
                jobs.append(Job(
                    id=f"workday:{company}:{path}", title=info.get("title") or p["title"], company=company,
                    location=location, url=info.get("externalUrl") or f"https://{host}/en-US/{site}{path}",
                    description=_strip_html(info.get("jobDescription", ""))[:3000], source=f"{company} Careers",
                    remote=remote, posted=info.get("startDate", ""),
                ))
    return jobs


def ibm(queries: list[str]) -> list[Job]:
    jobs, seen = [], set()
    fields = ["keywords^1", "body^1", "url^2", "description^2", "h1s_content^2", "title^3", "field_keyword_05^2"]
    for q in _queries(queries):
        body = {
            "appId": "careers", "scopes": ["careers2"], "size": 50, "from": 0, "lang": "zz",
            "query": {"bool": {"must": [{"simple_query_string": {"query": q, "fields": fields}}]}},
            "sort": [{"dcdate": "desc"}],
            "_source": ["title", "url", "description", "field_keyword_05", "field_keyword_17", "field_keyword_19", "dcdate"],
        }
        try:
            r = requests.post("https://www-api.ibm.com/search/api/v2", json=body, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            hits = r.json().get("hits", {}).get("hits", [])
        except Exception as e:
            logging.warning("IBM failed for %r: %s", q, e)
            continue
        for h in hits:
            s = h.get("_source", {})
            url = s.get("url")
            if not url or url in seen or not _title_matches(s.get("title", ""), _title_keywords()):
                continue
            seen.add(url)
            location = s.get("field_keyword_19", "")
            remote = (s.get("field_keyword_17") or "").lower() == "remote" or is_remote(location)
            if not _wanted(remote, location, s.get("field_keyword_05") == "United States"):
                continue
            jobs.append(Job(
                id=f"ibm:{url}", title=s.get("title", ""), company="IBM", location=location or "Remote", url=url,
                description=_strip_html(s.get("description", ""))[:3000], source="IBM Careers",
                remote=remote, posted=s.get("dcdate", ""),
            ))
    return jobs


def microsoft(queries: list[str]) -> list[Job]:
    jobs, seen = [], set()
    for q in _queries(queries):
        try:
            r = requests.get(
                "https://apply.careers.microsoft.com/api/pcsx/search",
                params={"domain": "microsoft.com", "query": q, "location": "United States", "start": 0, "sort_by": "timestamp"},
                headers=HEADERS, timeout=TIMEOUT,
            )
            if r.status_code == 429:
                time.sleep(5)
                r = requests.get(r.url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            positions = r.json().get("data", {}).get("positions", [])
        except Exception as e:
            logging.warning("Microsoft failed for %r: %s", q, e)
            continue
        time.sleep(2)
        for p in positions:
            pid = str(p.get("id"))
            if pid in seen:
                continue
            seen.add(pid)
            locs = p.get("standardizedLocations") or p.get("locations") or []
            location = "; ".join(locs[:3])
            remote = (p.get("workLocationOption") or "").lower() == "remote"
            if not _wanted(remote, location, True):
                continue
            jobs.append(Job(
                id=f"msft:{pid}", title=p.get("name", ""), company="Microsoft", location=location or "Remote",
                url=f"https://apply.careers.microsoft.com{p.get('positionUrl', '')}",
                description=f"Department: {p.get('department', '')}. Work option: {p.get('workLocationOption', '')}.",
                source="Microsoft Careers", remote=remote,
            ))
    return jobs


def greenhouse(_queries: list[str]) -> list[Job]:
    jobs, kw = [], _title_keywords()
    for board in config.GREENHOUSE_BOARDS:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"}, headers=HEADERS, timeout=60)
            r.raise_for_status()
            postings = r.json().get("jobs", [])
        except Exception as e:
            logging.warning("Greenhouse %s failed: %s", board, e)
            continue
        for p in postings:
            location = (p.get("location") or {}).get("name", "")
            remote = is_remote(location)
            if not _title_matches(p.get("title", ""), kw) or not _wanted(remote, location, looks_us(location) or location.strip().lower() in ("remote", "")):
                continue
            jobs.append(Job(
                id=f"gh:{board}:{p['id']}", title=p.get("title", ""), company=p.get("company_name") or board.title(),
                location=location, url=p.get("absolute_url", ""),
                description=_strip_html(html.unescape(p.get("content", "")))[:3000],
                source=f"{board.title()} Careers", remote=remote, posted=(p.get("updated_at") or "")[:10],
            ))
    return jobs


def lever(_queries: list[str]) -> list[Job]:
    jobs, kw = [], _title_keywords()
    for co in config.LEVER_COMPANIES:
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{co}", params={"mode": "json"}, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            postings = r.json()
        except Exception as e:
            logging.warning("Lever %s failed: %s", co, e)
            continue
        for p in postings:
            cats = p.get("categories") or {}
            location = cats.get("location", "")
            remote = (p.get("workplaceType") or "").lower() == "remote" or is_remote(location)
            if not _title_matches(p.get("text", ""), kw) or not _wanted(remote, location, looks_us(location) or location.strip().lower() in ("remote", "")):
                continue
            jobs.append(Job(
                id=f"lever:{co}:{p['id']}", title=p.get("text", ""), company=co.title(), location=location or "Remote",
                url=p.get("hostedUrl", ""), description=(p.get("descriptionPlain") or "")[:3000],
                source=f"{co.title()} Careers", remote=remote,
            ))
    return jobs


# --- Extra free job boards ------------------------------------------------

def himalayas(queries: list[str]) -> list[Job]:
    jobs, seen = [], set()
    for q in _queries(queries):
        try:
            r = requests.get("https://himalayas.app/jobs/api/search", params={"q": q, "country": "US", "sort": "recent"}, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            postings = r.json().get("jobs", [])
        except Exception as e:
            logging.warning("Himalayas failed for %r: %s", q, e)
            continue
        for p in postings:
            url = p.get("applicationLink") or p.get("guid")
            if not url or url in seen or not _title_matches(p.get("title", ""), _title_keywords()):
                continue
            seen.add(url)
            jobs.append(Job(
                id=f"himalayas:{url}", title=p.get("title", ""), company=p.get("companyName", ""),
                location=", ".join(p.get("locationRestrictions") or []) or "Remote", url=url,
                description=_strip_html(p.get("excerpt", ""))[:3000], source="Himalayas", remote=True,
            ))
    return jobs
