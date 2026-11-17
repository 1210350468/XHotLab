Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (!(Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python 3.12 and Windows Python Launcher (py.exe) are required.'
}
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Install Git for Windows before running this installer.'
}
if (!(Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js LTS with npm.cmd before running this installer.'
}

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
    & py -3.12 -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the XHotLab virtual environment.' }
}
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'XHotLab Python dependency installation failed.' }

& npm.cmd ci --prefix (Join-Path $PSScriptRoot 'integrations') --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'XHotLab Node.js dependency installation failed.' }

$creatorhubRoot = if ($env:CREATORHUB_HOME) { $env:CREATORHUB_HOME } else {
    Join-Path (Split-Path -Parent $PSScriptRoot) 'CreatorHub'
}
if (!(Test-Path -LiteralPath $creatorhubRoot)) {
    & git clone -- https://github.com/3441293738/creatorhub.git $creatorhubRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not clone CreatorHub from GitHub.' }
}
$installer = Join-Path $creatorhubRoot 'creatorhub.py'
if (!(Test-Path -LiteralPath $installer)) {
    throw "CreatorHub installer was not found: $installer"
}
Push-Location -LiteralPath $creatorhubRoot
& $python creatorhub.py install
$installExitCode = $LASTEXITCODE
Pop-Location
if ($installExitCode -ne 0) { throw 'CreatorHub installation failed.' }

if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    !(Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg and FFprobe must be installed and available on PATH for video publishing.'
}
Write-Output 'XHotLab and CreatorHub are installed. Run .\start.ps1 to launch.'
