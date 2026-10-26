param([Parameter(ValueFromRemainingArguments = $true)][string[]]$VibeArguments)
$ErrorActionPreference = 'Stop'
$vibePython = @('.venv/Scripts/python.exe', '.venv/bin/python') |
    ForEach-Object { Join-Path $PSScriptRoot $_ } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if ($vibePython) {
    & $vibePython (Join-Path $PSScriptRoot 'vibe.py') @VibeArguments
} else {
    $vibePythonNames = if ([Environment]::OSVersion.Platform -eq 'Win32NT') { @('python', 'python3') } else { @('python3', 'python') }
    $vibePythonCommand = $vibePythonNames | ForEach-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
    if (-not $vibePythonCommand) { throw 'Install Python 3.10+ and follow README.md to install dependencies.' }
    & $vibePythonCommand.Source (Join-Path $PSScriptRoot 'vibe.py') @VibeArguments
}
exit $LASTEXITCODE
