param([int]$Port = 8000, [switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run the Python setup steps in README.md first.'
}
$dataDirectory = Join-Path $projectRoot 'backend/data'
New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null
$serverRunning = $false
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    $serverRunning = $health.app -eq 'Tushum AI'
} catch {}
if (-not $serverRunning) {
    $serviceProcess = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', "$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataDirectory 'server.log') -RedirectStandardError (Join-Path $dataDirectory 'server-error.log')
    $serviceProcess.Id | Set-Content -LiteralPath (Join-Path $dataDirectory 'server.pid')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($serviceProcess.HasExited) { throw 'Server failed to start. Check backend/data/server-error.log.' }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
            if ($health.app -eq 'Tushum AI') { $serverRunning = $true; break }
        } catch {}
    }
    if (-not $serverRunning) { throw 'Server startup timed out. Check backend/data/server-error.log.' }
}
Write-Host "Tushum AI ishga tushdi. http://localhost:$Port"
[Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName()) | Where-Object { $_.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and -not [Net.IPAddress]::IsLoopback($_) -and $_.IPAddressToString -notlike '169.254.*' } | ForEach-Object { Write-Host "Telefon uchun manzil http://$($_.IPAddressToString):$Port" }
if ($OpenBrowser) { Start-Process "http://localhost:$Port" }
