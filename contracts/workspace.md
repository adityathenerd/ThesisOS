# Desktop workspace and credential setup

User decision on 24 October 2026: put the project on the Desktop and edit it there.

Canonical editing path: `C:/Users/ASUS/Desktop/ThesisOS`.

This is an NTFS directory junction to the original shared app folder under this chat's outputs. It is the same files, not a copy. Existing commands through the old path continue to work without interrupting active builds. Use Desktop paths in new edits, launch commands and user instructions. Do not delete either path during this build.

Master control owns `scripts/Set-CrustdataKey.ps1`, root secret ignore rules, and this workspace note. Existing module ownership otherwise stays unchanged.

The backend settings loader currently reads `config/.env` and the `CRUSTDATA_API_KEY` variable. The helper script prompts with hidden input, preserves other environment entries, writes the key to that ignored file, and sets it for the current PowerShell process. It does not enable live provider mode or prove that a key works. Restart an already-running backend after saving configuration.

PowerShell command from any directory:

```powershell
Set-Location 'C:\Users\ASUS\Desktop\ThesisOS'
& .\scripts\Set-CrustdataKey.ps1
```

Reference thesis remains awaiting the user. Never put secrets in the frontend, handoffs, screenshots, logs or source control.

The user supplied https://app.crustdata.com/endpoints. In this control chat's browser it redirects to a sign-in page, so account-specific endpoint access is unverified. Public official references for adapter preparation include https://crustdata.com/company-data-api and https://crustdata.com/people-api. The company API page documents POST /company/search and POST /company/enrich on https://api.crustdata.com with Bearer authentication and x-api-version 2025-11-01. Confirm detailed filter and response schemas against official endpoint docs before implementing mappings; do not mix legacy screener examples with versioned company routes. Do not consume provider credits as part of this workspace setup.


## Credential setup correction and agent package

The user encountered PSSecurityException when invoking .ps1 scripts because script execution is disabled. The existing helper remains available for other environments, but direct editing is the working setup alternative on this machine. Use `notepad C:\Users\ASUS\Desktop\ThesisOS\config\.env` for CRUSTDATA_API_KEY, and `notepad C:\Users\ASUS\Desktop\ThesisOS\agents\.env` for OPENAI_API_KEY once that directory exists. Preserve other entries; do not change execution policy. Restart/reload the owning runtime as documented. Key presence does not enable live mode by itself.

The existing agent-design chat is now authorized by the human to implement the agents/ package, dependencies and mocked boundary tests. It owns agents/, planning/agents/ and handoffs/agents-design.md. Backend and frontend ownership is unchanged. See handoffs/control-agent-runtime.md for integration checkpoints.
