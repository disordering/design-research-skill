param([ValidateSet('original','copy')][string]$Mode = 'original')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($Mode -eq 'copy' -and !(Test-Path -LiteralPath (Join-Path $repo 'out/b-engine-copy/engine/__main__.py'))) { throw 'Temporary engine copy is missing. This frontend package does not include it.' }
New-Item -ItemType Directory -Path (Join-Path $repo 'out') -Force | Out-Null
$choice = @{enabled = ($Mode -eq 'copy'); path = 'out/b-engine-copy'}
$choice | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $repo 'out/backend-selection.json') -Encoding utf8
Write-Host "Next startup uses: $Mode. Restart the backend to apply; existing sessions are retained."
