param([Parameter(ValueFromRemainingArguments = $true)][string[]]$VibeArguments)
$ErrorActionPreference = 'Stop'
$vibePython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $vibePython) {
    & $vibePython (Join-Path $PSScriptRoot 'vibe.py') @VibeArguments
} else {
    $vibePythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $vibePythonCommand) { throw '请先安装 Python 3.10+，然后按 README.md 安装依赖' }
    & $vibePythonCommand.Source (Join-Path $PSScriptRoot 'vibe.py') @VibeArguments
}
exit $LASTEXITCODE
