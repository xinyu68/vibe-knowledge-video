$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.local\n8n\bridge.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'No bridge process record. n8n was not changed.'; return }
$savedProcessId = (Get-Content -LiteralPath $pidFile -Raw).Trim()
if ($savedProcessId -notmatch '^\d+$') { throw 'Invalid bridge process record.' }
$processes = @(Get-CimInstance Win32_Process)
$rootProcess = $processes | Where-Object { $_.ProcessId -eq [int]$savedProcessId }
if (-not $rootProcess) { Write-Output 'Bridge is already stopped. n8n was not changed.'; return }
$bridgePath = Join-Path $PSScriptRoot 'n8n_bridge.py'
if (-not $rootProcess.CommandLine -or -not $rootProcess.CommandLine.Contains($bridgePath)) {
    throw 'The recorded process does not belong to this bridge. No process was stopped.'
}
& taskkill.exe /PID ([string]$rootProcess.ProcessId) /T /F
if ($LASTEXITCODE -ne 0) { throw 'The bridge process tree could not be fully stopped. Check its processes before retrying.' }
Write-Output 'Video bridge stopped. Files and n8n are retained; interrupted jobs can be retried after restart.'
