$ErrorActionPreference = 'Stop'
$backend = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $backend '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw '未找到仓库自己的.venv。请按D交付说明，使用Python3.11或3.12创建环境并安装requirements-session.txt。' }
Set-Location -LiteralPath $backend
& $python (Join-Path $PSScriptRoot 'check-setup.py')
if ($LASTEXITCODE -ne 0) { throw '启动前自检未通过，请按上面的缺项处理。' }
Remove-Item Env:REVIEW_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:REVIEW_ALLOW_STUB -ErrorAction SilentlyContinue
& $python (Join-Path $PSScriptRoot 'backend-launch.py') $backend
