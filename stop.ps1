[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$thesisRuntimePath = Join-Path $PSScriptRoot 'demo\.runtime.json'
if (-not (Test-Path -LiteralPath $thesisRuntimePath)) { Write-Host 'No launcher-owned processes recorded.'; return }
$thesisRecorded = @((Get-Content -Raw -LiteralPath $thesisRuntimePath | ConvertFrom-Json).processes)
function Stop-ThesisTree([int]$thesisProcessId) {
    # Windows venv launchers can have a real Python child; stop only this owned tree.
    $thesisChildren = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$thesisProcessId" -ErrorAction SilentlyContinue)
    foreach ($thesisDescendant in $thesisChildren) { Stop-ThesisTree $thesisDescendant.ProcessId }
    Stop-Process -Id $thesisProcessId -ErrorAction SilentlyContinue
}
foreach ($thesisEntry in $thesisRecorded) {
    $thesisChild = Get-Process -Id $thesisEntry.id -ErrorAction SilentlyContinue
    if ($null -ne $thesisChild -and $thesisChild.StartTime.ToUniversalTime().Ticks -eq ([datetime]$thesisEntry.started).ToUniversalTime().Ticks) {
        Stop-ThesisTree $thesisChild.Id
        Write-Host "Stopped launcher-owned $($thesisEntry.name) (PID $($thesisEntry.id))."
    }
}
@{ processes=@() } | ConvertTo-Json | Set-Content -LiteralPath $thesisRuntimePath -Encoding utf8
