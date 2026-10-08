import logging
from datetime import datetime, timezone

from . import config, matcher, notify, sources, store


def run() -> dict:
    resume = store.load_resume_text()
    profile = matcher.extract_profile(resume)
    if config.TARGET_TITLES:
        profile["titles"] = config.TARGET_TITLES
    logging.info("Profile titles: %s", profile.get("titles"))

    seen = store.load_seen()
    jobs = [j for j in sources.fetch_all(profile.get("titles", [])) if j.id not in seen]
    candidates = matcher.prerank(jobs, profile)
    scored = matcher.score_jobs(candidates, resume, profile)

    now = datetime.now(timezone.utc).isoformat()
    for j in scored:
        seen[j.id] = now
    store.save_seen(seen)

    matches = [j for j in scored if j.score >= config.MIN_SCORE]
    if matches:
        notify.send_digest(matches)
    return {"new_jobs": len(jobs), "scored": len(scored), "matches": len(matches)}
