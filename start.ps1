Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $pythonw)) {
    throw 'XHotLab environment is missing. Run .\install.ps1 first.'
}
$url = 'http://127.0.0.1:8766'
$running = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if (!$running) {
    $process = Start-Process -FilePath $pythonw -ArgumentList @('-m', 'app.background_service') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        if ($process.HasExited) {
            throw 'XHotLab service exited. See logs\server.stderr.log.'
        }
        $listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            $ready = $true
            break
        }
    }
    if (!$ready) {
        throw 'XHotLab did not listen on port 8766. See logs\server.stderr.log.'
    }
}
$health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 5
if (!$health.ok -or $health.service -ne 'XHotLab') {
    throw 'Port 8766 is occupied or the XHotLab health check failed.'
}
Write-Output "XHotLab ready: $url"

$creatorhubRoot = if ($env:CREATORHUB_HOME) { $env:CREATORHUB_HOME } else {
    Join-Path (Split-Path -Parent $PSScriptRoot) 'CreatorHub'
}
$creatorhubPython = Join-Path $creatorhubRoot '.venv\Scripts\pythonw.exe'
if (Test-Path -LiteralPath $creatorhubPython) {
    $headers = @{'X-XHotLab-Action' = '1'}
    $creatorhub = Invoke-RestMethod -Method Post -Uri "$url/api/creatorhub/start" -Headers $headers -TimeoutSec 30
    if (!$creatorhub.running) {
        throw 'CreatorHub health check failed. See CreatorHub\data\logs.'
    }
    Write-Output "CreatorHub ready: $($creatorhub.url)"
} else {
    Write-Warning 'CreatorHub is missing. Run .\install.ps1 for multi-platform functions.'
}
