param([Parameter(Mandatory = $true)][string]$N8nDirectory)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$N8nDirectory = (Resolve-Path -LiteralPath $N8nDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $N8nDirectory 'start-n8n.ps1'))) {
    throw 'This helper expects an existing n8n-studio installation. For another setup follow docs/n8n工作流.md.'
}
$source = Join-Path $projectRoot 'integrations\n8n\VibeVideo.node.js'
$destination = Join-Path $N8nDirectory 'custom-nodes\VibeVideo.node.js'
if (-not (Test-Path -LiteralPath $source)) { throw 'Missing integrations/n8n/VibeVideo.node.js.' }
if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $source).Hash -eq (Get-FileHash -LiteralPath $destination).Hash) {
    Write-Output 'The custom node is already installed with the current source.'
    return
}
if (Get-NetTCPConnection -State Listen -LocalPort 5678 -ErrorAction SilentlyContinue) {
    throw 'n8n must be stopped before installing a new custom node. Finish active work, stop this n8n installation, then run this helper again.'
}
New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
if (Test-Path -LiteralPath $destination) {
    $backupDirectory = Join-Path $projectRoot '.local\n8n\node-backups'
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination (Join-Path $backupDirectory ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-VibeVideo.node.js'))
}
Copy-Item -LiteralPath $source -Destination $destination -Force
Write-Output 'Custom node installed. Start n8n, then import integrations/n8n/workflow.json into a NEW workflow.'
Write-Output 'Existing workflows were not modified; reimporting is a separate explicit step so canvas edits are preserved.'
