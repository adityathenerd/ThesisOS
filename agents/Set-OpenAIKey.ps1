[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$agentEnvPath = Join-Path $PSScriptRoot '.env'
$agentSecureKey = Read-Host 'Paste your OpenAI API key (input is hidden)' -AsSecureString
$agentPlainKey = ([System.Net.NetworkCredential]::new('', $agentSecureKey)).Password

try {
    if ([string]::IsNullOrWhiteSpace($agentPlainKey) -or $agentPlainKey -match '[\r\n\x00]') {
        throw 'Enter a nonempty API key on one line.'
    }
    $agentExistingLines = if (Test-Path -LiteralPath $agentEnvPath) {
        @([System.IO.File]::ReadAllLines($agentEnvPath))
    } else { @() }
    $agentKeptLines = @($agentExistingLines | Where-Object { $_ -notmatch '^\s*(export\s+)?OPENAI_API_KEY\s*=' })
    $agentEscapedKey = $agentPlainKey.Replace('\', '\\').Replace("'", "\'")
    $agentKeyLine = "OPENAI_API_KEY='$agentEscapedKey'"
    [System.IO.File]::WriteAllText($agentEnvPath, ((@($agentKeptLines) + @($agentKeyLine)) -join [Environment]::NewLine) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    $env:OPENAI_API_KEY = $agentPlainKey
    Write-Host 'OpenAI key saved to agents\.env and set for this PowerShell session.'
    Write-Host 'No API request was made. Crustdata configuration was not changed.'
} finally {
    $agentPlainKey = $null
    $agentEscapedKey = $null
    $agentKeyLine = $null
    if ($null -ne $agentSecureKey) { $agentSecureKey.Dispose() }
}
