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

LOCAL_LOCATIONS = [x.strip() for x in _get("LOCAL_LOCATIONS", "Greenville, SC;Spartanburg, SC").split(";") if x.strip()]
LOCAL_RADIUS_MILES = int(_get("LOCAL_RADIUS_MILES", "30"))
MIN_SCORE = int(_get("MIN_SCORE", "65"))
MAX_RESULTS_IN_EMAIL = int(_get("MAX_RESULTS_IN_EMAIL", "20"))
MAX_JOBS_TO_SCORE = int(_get("MAX_JOBS_TO_SCORE", "60"))
# Optional free-text preferences passed to the AI (salary, seniority, exclusions...)
PREFERENCES = _get("JOB_PREFERENCES", "")
