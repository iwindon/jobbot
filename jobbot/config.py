import os


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


OPENAI_ENDPOINT = _get("AZURE_OPENAI_ENDPOINT")
OPENAI_DEPLOYMENT = _get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
STORAGE_CONNECTION = _get("AzureWebJobsStorage")
CONTAINER = _get("JOBBOT_CONTAINER", "jobbot")

ACS_CONNECTION_STRING = _get("ACS_CONNECTION_STRING")
EMAIL_SENDER = _get("EMAIL_SENDER")
EMAIL_TO = [e.strip() for e in _get("EMAIL_TO").split(";") if e.strip()]

ADZUNA_APP_ID = _get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = _get("ADZUNA_APP_KEY")
USAJOBS_API_KEY = _get("USAJOBS_API_KEY")
USAJOBS_EMAIL = _get("USAJOBS_EMAIL")

LOCAL_LOCATIONS = [x.strip() for x in _get("LOCAL_LOCATIONS", "Greenville, SC;Spartanburg, SC").split(";") if x.strip()]
LOCAL_RADIUS_MILES = int(_get("LOCAL_RADIUS_MILES", "30"))
MIN_SCORE = int(_get("MIN_SCORE", "65"))
MAX_RESULTS_IN_EMAIL = int(_get("MAX_RESULTS_IN_EMAIL", "20"))
MAX_JOBS_TO_SCORE = int(_get("MAX_JOBS_TO_SCORE", "60"))
# Optional free-text preferences passed to the AI (salary, seniority, exclusions...)
PREFERENCES = _get("JOB_PREFERENCES", "")
# Semicolon-separated titles to search for; overrides titles inferred from the resume
TARGET_TITLES = [t.strip() for t in _get("TARGET_TITLES").split(";") if t.strip()]

# Company career sites. Workday entries are 'company|host|site'; others are board/company slugs.
WORKDAY_SITES = [x.strip() for x in _get("WORKDAY_SITES", "Red Hat|redhat.wd5.myworkdayjobs.com|Jobs").split(";") if x.strip()]
GREENHOUSE_BOARDS = [x.strip() for x in _get("GREENHOUSE_BOARDS", "cloudflare,datadog,mongodb,okta,twilio,elastic,canonical").split(",") if x.strip()]
LEVER_COMPANIES = [x.strip() for x in _get("LEVER_COMPANIES", "palantir,spotify").split(",") if x.strip()]
