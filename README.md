# jobbot

AI job-search bot on Azure Functions (Python). Every day at 8am ET it:

1. Reads your resume from Blob Storage and has Azure OpenAI extract target titles and skills.
2. Searches remote boards (Remotive, RemoteOK, Himalayas), company career sites (Red Hat via Workday, IBM, Microsoft, plus Greenhouse/Lever boards for Cloudflare, Datadog, MongoDB, Okta, Twilio, Elastic, Canonical, Palantir, Spotify) and local jobs for Greenville/Spartanburg, SC (Adzuna, plus federal jobs from USAJOBS, which needs `USAJOBS_API_KEY` and `USAJOBS_EMAIL`). Company jobs are kept only if they are US-eligible remote or in the SC area, and title-filtered to `TARGET_TITLES`. WeWorkRemotely is excluded because its listings are paywalled.
3. Skips jobs already seen, pre-ranks by keyword overlap, then has the LLM score the top candidates against your resume.
4. Emails you matches at or above `MIN_SCORE` via Azure Communication Services.

Auth to Azure OpenAI uses the function's managed identity (no keys).

## Deploy

Prereqs: Azure CLI (`az login`) and a free Adzuna key from https://developer.adzuna.com (needed for local jobs).

```powershell
./scripts/deploy.ps1 -ResourceGroup jobbot-rg -EmailTo you@example.com -ResumePath C:\path\resume.pdf `
  -AdzunaAppId <id> -AdzunaAppKey <key> -JobPreferences "Senior roles only, min $120k, no contract"
```

Trigger a run on demand: `POST https://<func>.azurewebsites.net/api/run?code=<function key>`.
Update the resume by re-uploading `resume.<ext>` to the `jobbot` container. Tune via app settings
(`MIN_SCORE`, `TARGET_TITLES` (semicolon-separated; overrides resume-derived titles), `LOCAL_LOCATIONS`, `LOCAL_RADIUS_MILES`, `JOB_PREFERENCES`, `MAX_RESULTS_IN_EMAIL`).

Notes:
- Azure OpenAI and ACS email-managed-domain require subscription access/quota in the chosen region; the DataZoneStandard gpt-5.4-mini deployment (override `openAiSku`/`openAiModel` to match your quota; list models with `az cognitiveservices model list -l eastus2`) is used.
- Azure-managed email domains have low sending limits and may land in spam on first sends; check junk.
- Rotating the resume is the only place PII lives; the storage account has no public blob access.

## CI/CD (GitHub Actions)

[.github/workflows/deploy.yml](.github/workflows/deploy.yml) deploys on every push to `main` that touches the code. One-time setup after pushing this repo to GitHub:

```powershell
./scripts/setup-github-oidc.ps1 -GitHubRepo <owner>/<repo>
```

This creates an Entra app with a federated credential limited to the `main` branch (no stored passwords), grants it Website Contributor on the function app only, and sets the repo secrets/variables (via `gh` if installed, otherwise it prints them).

## Local run
Copy `local.settings.sample.json` to `local.settings.json`, run Azurite, `az login`, then `func start` and call `/api/run`.
