param(
    [string]$N8nDirectory,
    [string]$TtsCli,
    [string]$WorkflowUrl,
    [int]$Port = 0,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$stateDirectory = Join-Path $projectRoot '.local\n8n'
$settingsFile = Join-Path $stateDirectory 'settings.json'
$settings = @{}
if (Test-Path -LiteralPath $settingsFile) {
    $saved = Get-Content -LiteralPath $settingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($property in $saved.PSObject.Properties) { $settings[$property.Name] = $property.Value }
}
if (-not $N8nDirectory) { $N8nDirectory = $settings.n8n_directory }
if (-not $N8nDirectory) {
    $sibling = Join-Path (Split-Path -Parent $projectRoot) 'n8n-studio'
    if (Test-Path -LiteralPath (Join-Path $sibling 'start-n8n.ps1')) { $N8nDirectory = $sibling }
}
if (-not $TtsCli) { $TtsCli = $env:VIBE_TTS_CLI }
if (-not $TtsCli) { $TtsCli = $settings.tts_cli }
if (-not $Port) { $Port = if ($settings.port) { [int]$settings.port } else { 5681 } }
if (-not $WorkflowUrl) { $WorkflowUrl = $settings.workflow_url }
if (-not $WorkflowUrl) { $WorkflowUrl = 'http://127.0.0.1:5678/home/workflows' }
$workflowUri = [Uri]$WorkflowUrl
if (-not $workflowUri.IsAbsoluteUri -or $workflowUri.Scheme -ne 'http' -or
    $workflowUri.Host -notin @('127.0.0.1', 'localhost') -or $workflowUri.UserInfo -or
    $workflowUri.Query -or $workflowUri.Fragment -or
    ($workflowUri.AbsolutePath -notmatch '^/workflow/[A-Za-z0-9_-]+/?$' -and $workflowUri.AbsolutePath -ne '/home/workflows')) {
    throw 'WorkflowUrl must be the local n8n workflow URL or local /home/workflows page.'
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
if (-not $TtsCli -or -not (Test-Path -LiteralPath $TtsCli -PathType Leaf)) {
    throw 'Pass -TtsCli pointing to your installed ttsCN scripts/tts.py (or set VIBE_TTS_CLI).'
}
$TtsCli = (Resolve-Path -LiteralPath $TtsCli).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$bridge = Join-Path $PSScriptRoot 'n8n_bridge.py'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create the project .venv and install requirements-tts.txt first.' }
if (-not (Test-Path -LiteralPath $bridge)) { throw 'Missing tools/n8n_bridge.py.' }
if ($N8nDirectory) {
    $N8nDirectory = (Resolve-Path -LiteralPath $N8nDirectory).Path
    $startN8n = Join-Path $N8nDirectory 'start-n8n.ps1'
    if (-not (Test-Path -LiteralPath $startN8n)) { throw 'N8nDirectory must contain start-n8n.ps1; for other installations start n8n separately.' }
    & $startN8n -NoBrowser
}

New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$settings.n8n_directory = $N8nDirectory
$settings.tts_cli = $TtsCli
$settings.port = $Port
$settings.workflow_url = $WorkflowUrl
[IO.File]::WriteAllText($settingsFile, ($settings | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
$baseUrl = "http://127.0.0.1:$Port"
$health = $null
try { $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 2 } catch { }
if ($health) {
    if ($health.service -ne 'vibe-video-bridge' -or $health.project_root -ne $projectRoot) {
        throw "Port $Port is occupied by a different service or project. No process was stopped."
    }
    Write-Output "Video bridge is already ready: $baseUrl"
} else {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is occupied. Choose another port and update the workflow bridge URL."
    }
    $previousTts = $env:VIBE_TTS_CLI
    $previousUtf8 = $env:PYTHONUTF8
    try {
        $env:VIBE_TTS_CLI = $TtsCli
        $env:PYTHONUTF8 = '1'
        $arguments = @('-u', ('"' + $bridge + '"'), '--port', [string]$Port)
        $process = Start-Process -FilePath $python -ArgumentList $arguments `
            -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $stateDirectory 'bridge.stdout.log') `
            -RedirectStandardError (Join-Path $stateDirectory 'bridge.stderr.log')
        [IO.File]::WriteAllText((Join-Path $stateDirectory 'bridge.pid'), [string]$process.Id)
    } finally {
        $env:VIBE_TTS_CLI = $previousTts
        $env:PYTHONUTF8 = $previousUtf8
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 1
            if ($health.service -eq 'vibe-video-bridge' -and $health.project_root -eq $projectRoot) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Bridge startup failed. See .local/n8n/bridge.stderr.log.' }
    Write-Output "Video bridge is ready: $baseUrl"
}
Write-Output "Workflow: $WorkflowUrl"
if (-not $NoBrowser) { Start-Process $WorkflowUrl }
