[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$thesisRoot=$PSScriptRoot
$thesisPython=Join-Path $thesisRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $thesisPython)) {
    if (Get-Command py.exe -ErrorAction SilentlyContinue) { & py.exe -3 -m venv (Join-Path $thesisRoot 'backend\.venv') }
    else { & python.exe -m venv (Join-Path $thesisRoot 'backend\.venv') }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $thesisPython)) { throw 'Install Python 3.12+ locally, then rerun setup. No global dependencies are installed.' }
}
& $thesisPython -m pip install -r (Join-Path $thesisRoot 'backend\requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Push-Location (Join-Path $thesisRoot 'frontend')
try { & npm.cmd ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } } finally { Pop-Location }
Write-Host 'Task-local dependencies ready. Run .\launch.ps1.'

