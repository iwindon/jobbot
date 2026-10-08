import json
import logging
import re

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from . import config
from .models import Job

_client = None


def _llm() -> AzureOpenAI:
    global _client
    if _client is None:
        token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
        _client = AzureOpenAI(
            azure_endpoint=config.OPENAI_ENDPOINT, azure_ad_token_provider=token, api_version="2024-10-21"
        )
    return _client


def _chat_json(system: str, user: str) -> dict:
    resp = _llm().chat.completions.create(
        model=config.OPENAI_DEPLOYMENT,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def extract_profile(resume: str) -> dict:
    system = (
        "You analyze resumes for a job search. Return JSON: "
        '{"titles": [up to 5 best-fit job titles to search for], '
        '"keywords": [up to 25 important skills/technologies/domains], '
        '"summary": "2 sentence candidate summary"}'
    )
    prefs = f"\n\nCandidate preferences: {config.PREFERENCES}" if config.PREFERENCES else ""
    return _chat_json(system, resume[:12000] + prefs)


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]{2,}", s.lower()))


def prerank(jobs: list[Job], profile: dict) -> list[Job]:
    """Cheap keyword-overlap ranking so only the most promising jobs hit the LLM."""
    kws = {k.lower() for k in profile.get("keywords", [])}
    title_toks = set().union(*[_tokens(t) for t in profile.get("titles", [])]) if profile.get("titles") else set()

    def rank(j: Job) -> float:
        text = _tokens(j.title + " " + j.description)
        return 3 * len(_tokens(j.title) & title_toks) + len(text & kws)

    return sorted(jobs, key=rank, reverse=True)[: config.MAX_JOBS_TO_SCORE]


def score_jobs(jobs: list[Job], resume: str, profile: dict) -> list[Job]:
    system = (
        "You are a strict recruiter matching a candidate to jobs. For each job give a fit score 0-100 "
        "(skills, seniority, domain; penalize clear mismatches) and a one-sentence reason. "
        'Return JSON: {"results": [{"id": "<job id>", "score": <int>, "reason": "<text>"}]}'
    )
    prefs = f"\nPreferences: {config.PREFERENCES}" if config.PREFERENCES else ""
    by_id = {j.id: j for j in jobs}
    for i in range(0, len(jobs), 8):
        batch = jobs[i : i + 8]
        payload = [
            {"id": j.id, "title": j.title, "company": j.company, "location": j.location, "description": j.description[:1500]}
            for j in batch
        ]
        user = (
            f"Candidate summary: {profile.get('summary', '')}\nKey skills: {', '.join(profile.get('keywords', []))}{prefs}\n\n"
            f"Resume:\n{resume[:6000]}\n\nJobs:\n{json.dumps(payload)}"
        )
        try:
            for r in _chat_json(system, user).get("results", []):
                job = by_id.get(r.get("id"))
                if job:
                    job.score = int(r.get("score", 0))
                    job.reason = r.get("reason", "")
        except Exception as e:
            logging.warning("Scoring batch failed: %s", e)
    return jobs
