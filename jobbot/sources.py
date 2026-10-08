import logging
import re

import feedparser
import requests

from . import config
from .models import Job

HEADERS = {"User-Agent": "jobbot/1.0 (personal job search)"}
TIMEOUT = 30
US_OK = ("usa", "united states", "us", "worldwide", "anywhere", "north america", "americas", "remote", "")


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def _us_friendly(location: str) -> bool:
    loc = (location or "").lower().strip()
    if loc in US_OK:
        return True
    return any(k in loc for k in ("usa", "united states", "worldwide", "anywhere", "north america", "americas"))


def remotive(queries: list[str]) -> list[Job]:
    jobs = []
    for q in queries[:4]:
        try:
            r = requests.get("https://remotive.com/api/remote-jobs", params={"search": q, "limit": 50}, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            for j in r.json().get("jobs", []):
                if not _us_friendly(j.get("candidate_required_location", "")):
                    continue
                jobs.append(Job(
                    id=f"remotive:{j['id']}", title=j["title"], company=j["company_name"],
                    location=j.get("candidate_required_location") or "Remote", url=j["url"],
                    description=_strip_html(j.get("description", ""))[:3000], source="Remotive",
                    remote=True, posted=j.get("publication_date", "")[:10],
                ))
        except Exception as e:
            logging.warning("Remotive failed for %r: %s", q, e)
    return jobs


def remoteok(_queries: list[str]) -> list[Job]:
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json():
            if not isinstance(j, dict) or "id" not in j:
                continue
            if not _us_friendly(j.get("location", "")):
                continue
            jobs.append(Job(
                id=f"remoteok:{j['id']}", title=j.get("position", ""), company=j.get("company", ""),
                location=j.get("location") or "Remote", url=j.get("url", ""),
                description=_strip_html(j.get("description", ""))[:3000] + " " + " ".join(j.get("tags", [])),
                source="RemoteOK", remote=True, posted=(j.get("date") or "")[:10],
            ))
    except Exception as e:
        logging.warning("RemoteOK failed: %s", e)
    return jobs


def weworkremotely(_queries: list[str]) -> list[Job]:
    jobs = []
    try:
        feed = feedparser.parse("https://weworkremotely.com/remote-jobs.rss", request_headers=HEADERS)
        for e in feed.entries:
            company, _, title = e.title.partition(": ")
            jobs.append(Job(
                id=f"wwr:{e.get('id') or e.link}", title=title or e.title, company=company if title else "",
                location=e.get("region", "Remote"), url=e.link,
                description=_strip_html(e.get("summary", ""))[:3000], source="WeWorkRemotely",
                remote=True, posted=(e.get("published") or "")[:16],
            ))
    except Exception as e:
        logging.warning("WeWorkRemotely failed: %s", e)
    return jobs


def adzuna(queries: list[str]) -> list[Job]:
    """Local jobs (and remote jobs) via Adzuna. Requires a free API key."""
    if not (config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY):
        logging.warning("ADZUNA keys not set; skipping local job search")
        return []
    jobs = []
    km = int(config.LOCAL_RADIUS_MILES * 1.609)
    for where in config.LOCAL_LOCATIONS:
        for q in queries[:4]:
            try:
                r = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/us/search/1",
                    params={
                        "app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
                        "results_per_page": 30, "what": q, "where": where, "distance": km,
                        "max_days_old": 14, "sort_by": "date", "content-type": "application/json",
                    },
                    timeout=TIMEOUT,
                )
                r.raise_for_status()
                for j in r.json().get("results", []):
                    jobs.append(Job(
                        id=f"adzuna:{j['id']}", title=_strip_html(j.get("title", "")),
                        company=(j.get("company") or {}).get("display_name", ""),
                        location=(j.get("location") or {}).get("display_name", where),
                        url=j.get("redirect_url", ""), description=_strip_html(j.get("description", "")),
                        source="Adzuna", remote=False, posted=(j.get("created") or "")[:10],
                    ))
            except Exception as e:
                logging.warning("Adzuna failed for %r in %r: %s", q, where, e)
    return jobs


def fetch_all(queries: list[str]) -> list[Job]:
    seen, out = set(), []
    for fn in (remotive, remoteok, weworkremotely, adzuna):
        for j in fn(queries):
            if j.id not in seen and j.url:
                seen.add(j.id)
                out.append(j)
    logging.info("Fetched %d unique jobs", len(out))
    return out
