[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$thesisProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$thesisEnvPath = Join-Path $thesisProjectRoot 'config\.env'
$thesisSecureKey = Read-Host 'Paste your Crustdata API key (input is hidden)' -AsSecureString
$thesisPlainKey = ([System.Net.NetworkCredential]::new('', $thesisSecureKey)).Password

try {
    if ([string]::IsNullOrWhiteSpace($thesisPlainKey) -or $thesisPlainKey -match '[\r\n\x00]') {
        throw 'Enter a nonempty API key on one line.'
    }

    $thesisExistingLines = if (Test-Path -LiteralPath $thesisEnvPath) {
        @([System.IO.File]::ReadAllLines($thesisEnvPath))
    } else {
        @()
    }
    $thesisKeptLines = @($thesisExistingLines | Where-Object { $_ -notmatch '^\s*(export\s+)?CRUSTDATA_API_KEY\s*=' })
    $thesisEscapedKey = $thesisPlainKey.Replace('\', '\\').Replace("'", "\'")
    $thesisKeyLine = "CRUSTDATA_API_KEY='$thesisEscapedKey'"
    $thesisNewText = (@($thesisKeptLines) + @($thesisKeyLine)) -join [Environment]::NewLine
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $thesisEnvPath)) | Out-Null
    [System.IO.File]::WriteAllText($thesisEnvPath, $thesisNewText + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    $env:CRUSTDATA_API_KEY = $thesisPlainKey

    Write-Host 'Crustdata key saved to config\.env and set for this PowerShell session.'
    Write-Host 'Restart an already-running backend to load it. Provider mode has not been changed.'
} finally {
    $thesisPlainKey = $null
    $thesisEscapedKey = $null
    $thesisKeyLine = $null
    $thesisNewText = $null
    if ($null -ne $thesisSecureKey) { $thesisSecureKey.Dispose() }
}
