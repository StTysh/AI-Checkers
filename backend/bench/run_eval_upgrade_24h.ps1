param(
    [double]$Hours = 24.0,
    [double]$PollSeconds = 10.0,
    [string]$ManifestPath = (Join-Path $PSScriptRoot "report_eval_upgrade_24h.json"),
    [string]$OutputBaseDir = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) "output")
)

$Host.UI.RawUI.WindowTitle = "AI Checkers - 24h Evaluation Upgrade Runner"

$repoRoot = Split-Path $PSScriptRoot -Parent | Split-Path -Parent
$pythonExe = Join-Path $repoRoot "backend\venv\Scripts\python.exe"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path $OutputBaseDir "report_eval_upgrade_24h_$timestamp"
$logPath = Join-Path $runDir "runner.log"

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

Write-Host "Starting 24-hour evaluation upgrade run"
Write-Host "Manifest : $ManifestPath"
Write-Host "Output   : $runDir"
Write-Host "Log file : $logPath"
Write-Host "Hours    : $Hours"
Write-Host "Poll     : $PollSeconds"
Write-Host ""

& $pythonExe (Join-Path $PSScriptRoot "run_experiments.py") `
    --manifest $ManifestPath `
    --output-dir $runDir `
    --hours $Hours `
    --poll-seconds $PollSeconds 2>&1 | Tee-Object -FilePath $logPath

$exitCode = $LASTEXITCODE
Write-Host ""
Write-Host "Runner exit code: $exitCode"
Write-Host "Output directory : $runDir"
exit $exitCode
