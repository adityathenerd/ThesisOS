[CmdletBinding()]
param([switch]$Dev, [switch]$FixtureOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$thesisRoot = $PSScriptRoot
$thesisFrontend = Join-Path $thesisRoot 'frontend'
$thesisLogs = Join-Path $thesisRoot 'demo\logs'
$thesisRuntimePath = Join-Path $thesisRoot 'demo\.runtime.json'
New-Item -ItemType Directory -Path $thesisLogs -Force | Out-Null
$thesisOwned = @()
if (Test-Path -LiteralPath $thesisRuntimePath) {
    $thesisOwned = @((Get-Content -Raw -LiteralPath $thesisRuntimePath | ConvertFrom-Json).processes)
}
function Test-ThesisUrl([string]$Address, [string]$Expected) {
    try { return (Invoke-WebRequest -Uri $Address -TimeoutSec 2).Content -match $Expected } catch { return $false }
}
function Start-ThesisProcess([string]$Executable, [string]$Arguments, [string]$Directory, [string]$Name) {
    $thesisChild = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $thesisLogs "$Name.out.log") -RedirectStandardError (Join-Path $thesisLogs "$Name.err.log")
    Start-Sleep -Milliseconds 100
    if ($thesisChild.HasExited) { throw "$Name exited. See demo\logs\$Name.err.log" }
    return @{ id = $thesisChild.Id; started = $thesisChild.StartTime.ToUniversalTime().ToString('o'); name = $Name }
}
if (-not (Test-Path -LiteralPath (Join-Path $thesisFrontend 'node_modules'))) { throw 'Frontend dependencies missing. Run .\setup.ps1 first.' }
try {
    if (-not $FixtureOnly -and -not (Test-ThesisUrl 'http://127.0.0.1:8000/health' '"contract_version"\s*:\s*"0.1"')) {
        $thesisPython = Join-Path $thesisRoot 'backend\.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $thesisPython)) { throw 'Backend virtual environment missing. Run .\setup.ps1 first.' }
        $thesisOwned += Start-ThesisProcess $thesisPython '-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000' $thesisRoot 'backend'
        $thesisBackendReady = $false
        for ($thesisAttempt=0; $thesisAttempt -lt 30; $thesisAttempt++) {
            if (Test-ThesisUrl 'http://127.0.0.1:8000/health' '"contract_version"\s*:\s*"0.1"') { $thesisBackendReady=$true; break }
            Start-Sleep -Milliseconds 200
        }
        if (-not $thesisBackendReady) { throw 'Backend did not become healthy. Inspect demo\logs\backend.err.log. An occupied port is never stopped automatically.' }
    }
    if (-not (Test-ThesisUrl 'http://127.0.0.1:5173/' 'ThesisOS')) {
        if (-not $Dev) {
            Push-Location $thesisFrontend
            try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } } finally { Pop-Location }
        }
        $thesisEntry = if ($Dev) { 'start-dev.mjs' } else { 'start-preview.mjs' }
        $thesisNode = (Get-Command node.exe -ErrorAction Stop).Source
        $thesisOwned += Start-ThesisProcess $thesisNode ('"' + (Join-Path $thesisFrontend $thesisEntry) + '"') $thesisFrontend 'frontend'
        $thesisFrontendReady = $false
        for ($thesisAttempt=0; $thesisAttempt -lt 30; $thesisAttempt++) {
            if (Test-ThesisUrl 'http://127.0.0.1:5173/' 'ThesisOS') { $thesisFrontendReady=$true; break }
            Start-Sleep -Milliseconds 200
        }
        if (-not $thesisFrontendReady) { throw 'Frontend did not become ready. Inspect demo\logs\frontend.err.log. Port 5173 is strict.' }
    } else { Write-Host 'Existing frontend reused. To change preview/dev mode, stop the owned frontend with .\stop.ps1, then relaunch.' }
} finally {
    @{ processes = $thesisOwned } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $thesisRuntimePath -Encoding utf8
}
Write-Host 'ThesisOS: http://127.0.0.1:5173/'
Write-Host 'Backend: http://127.0.0.1:8000/docs (unless -FixtureOnly).'
Write-Host 'HTTP is the default transport. For browser-only fallback select Connection settings > Browser fixtures explicitly.'
Write-Host 'Stop only launcher-owned processes with .\stop.ps1. Existing running services were reused.'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173/' }
