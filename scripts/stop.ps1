$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pidFile = Join-Path $projectRoot 'backend/data/server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'No background server PID was recorded.'
    exit 0
}
$recordedServiceId = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$pythonPath = (Join-Path $projectRoot '.venv/Scripts/python.exe').Replace('/', '\')
$expectedCommand = '"' + $pythonPath + '" -m uvicorn backend.main:app '
$processes = @(Get-CimInstance Win32_Process -Filter "ProcessId=$recordedServiceId OR ParentProcessId=$recordedServiceId")
$serviceProcesses = @($processes | Where-Object { $_.CommandLine -and $_.CommandLine.StartsWith($expectedCommand, [StringComparison]::OrdinalIgnoreCase) })
if ($processes.Count -gt 0 -and $serviceProcesses.Count -eq 0) {
    throw 'The recorded PID belongs to a different process. No process was stopped.'
}
$serviceProcesses | Where-Object { $_.ProcessId -ne $recordedServiceId } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$serviceProcesses | Where-Object { $_.ProcessId -eq $recordedServiceId } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item -LiteralPath $pidFile
Write-Host 'Tushum AI server stopped.'
