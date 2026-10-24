[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$thesisRoot=$PSScriptRoot
foreach ($thesisComponent in @('backend','agents')) {
    $thesisEnvironment=Join-Path $thesisRoot ($thesisComponent+'\.venv')
    $thesisPython=Join-Path $thesisEnvironment 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $thesisPython)) {
        if (Get-Command py.exe -ErrorAction SilentlyContinue) { & py.exe -3.12 -m venv $thesisEnvironment }
        else { & python.exe -m venv $thesisEnvironment }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $thesisPython)) { throw 'Install Python 3.12+ locally, then rerun setup. No global dependencies are installed.' }
    }
    & $thesisPython -m pip install -r (Join-Path $thesisRoot ($thesisComponent+'\requirements.lock.txt'))
    if ($LASTEXITCODE -ne 0) { throw ($thesisComponent+' dependency installation failed.') }
}
Push-Location (Join-Path $thesisRoot 'frontend')
try { & npm.cmd ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } } finally { Pop-Location }
Write-Host 'Local backend, agent and frontend dependencies ready. Run .\launch.ps1.'
