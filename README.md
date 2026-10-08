# jobbot

AI job-search bot on Azure Functions (Python). Every day at 8am ET it:

1. Reads your resume from Blob Storage and has Azure OpenAI extract target titles and skills.
2. Searches remote boards (Remotive, RemoteOK, WeWorkRemotely) and local jobs for Greenville/Spartanburg, SC (Adzuna).
3. Skips jobs already seen, pre-ranks by keyword overlap, then has the LLM score the top candidates against your resume.
4. Emails you matches at or above `MIN_SCORE` via Azure Communication Services.

Auth to Azure OpenAI uses the function's managed identity (no keys).

## Deploy

Prereqs: Azure CLI (`az login`), Azure Functions Core Tools, and a free Adzuna key from https://developer.adzuna.com (needed for local jobs).

```powershell
./scripts/deploy.ps1 -ResourceGroup jobbot-rg -EmailTo you@example.com -ResumePath C:\path\resume.pdf `
  -AdzunaAppId <id> -AdzunaAppKey <key> -JobPreferences "Senior roles only, min $120k, no contract"
```

Trigger a run on demand: `POST https://<func>.azurewebsites.net/api/run?code=<function key>`.
Update the resume by re-uploading `resume.<ext>` to the `jobbot` container. Tune via app settings
(`MIN_SCORE`, `LOCAL_LOCATIONS`, `LOCAL_RADIUS_MILES`, `JOB_PREFERENCES`, `MAX_RESULTS_IN_EMAIL`).

Notes:
- Azure OpenAI and ACS email-managed-domain require subscription access/quota in the chosen region; the GlobalStandard gpt-4o-mini deployment is used.
- Azure-managed email domains have low sending limits and may land in spam on first sends; check junk.
- Rotating the resume is the only place PII lives; the storage account has no public blob access.

## Local run
Copy `local.settings.sample.json` to `local.settings.json`, run Azurite, `az login`, then `func start` and call `/api/run`.
