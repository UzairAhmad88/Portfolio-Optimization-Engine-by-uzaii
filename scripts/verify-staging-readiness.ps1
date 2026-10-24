<#
.SYNOPSIS
    Quantitative Portfolio Optimization Engine (QPE) — Staging Readiness Preflight Harness.
.DESCRIPTION
    Session 98 operational preflight script evaluating repository hygiene, configuration safety,
    secret policies, database migration readiness, network port isolation, and staging prerequisites.
.PARAMETER StagingUrl
    Optional external staging HTTPS URL (e.g. https://staging-qpe.internal.firm) to probe for TLS termination.
.PARAMETER LiveDbVerified
    Switch flag asserting that a live database backup/restore drill was verified on a provisioned staging host.
.PARAMETER Environment
    Target environment name (default: "staging").
.PARAMETER Json
    Outputs structured JSON payload instead of formatted console text.
.PARAMETER Strict
    Treat warnings as blocking failures.
.EXAMPLE
    .\scripts\verify-staging-readiness.ps1
.EXAMPLE
    .\scripts\verify-staging-readiness.ps1 -StagingUrl "https://staging.quantengine.internal" -LiveDbVerified
#>

[CmdletBinding()]
param(
    [string]$StagingUrl = "",
    [switch]$LiveDbVerified,
    [string]$Environment = "staging",
    [switch]$Json,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

# Determine repository root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

# Locate Python executable (prefer backend/.venv)
$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = Get-Command "python" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}

if (-not $PythonExe) {
    Write-Error "Python 3.11 executable not found in backend\.venv or on system PATH."
    exit 1
}

# Construct arguments for app.ops.staging_preflight
$PreflightModule = "app.ops.staging_preflight"
$BackendDir = Join-Path $RepoRoot "backend"

$ArgsList = @("-m", $PreflightModule, "--repo-root", "`"$RepoRoot`"", "--env", "`"$Environment`"")
if ($StagingUrl) {
    $ArgsList += @("--staging-url", "`"$StagingUrl`"")
}
if ($LiveDbVerified) {
    $ArgsList += "--live-db-verified"
}
if ($Strict) {
    $ArgsList += "--strict"
}
if ($Json) {
    $ArgsList += "--json"
}

# Execute python preflight harness
$env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"

$ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
$ProcessInfo.FileName = $PythonExe
$ProcessInfo.Arguments = ($ArgsList -join " ")
$ProcessInfo.WorkingDirectory = $BackendDir
$ProcessInfo.RedirectStandardOutput = $true
$ProcessInfo.RedirectStandardError = $true
$ProcessInfo.UseShellExecute = $false
$ProcessInfo.CreateNoWindow = $true

$Process = New-Object System.Diagnostics.Process
$Process.StartInfo = $ProcessInfo

$Process.Start() | Out-Null
$Stdout = $Process.StandardOutput.ReadToEnd()
$Stderr = $Process.StandardError.ReadToEnd()
$Process.WaitForExit()

$ExitCode = $Process.ExitCode

if ($Json) {
    Write-Output $Stdout
    if ($Stderr) {
        [Console]::Error.WriteLine($Stderr)
    }
    exit $ExitCode
}

# Colorized console output
foreach ($line in ($Stdout -split "`r?`n")) {
    if ($line -match "\[PASS\s*\]") {
        Write-Host $line -ForegroundColor Green
    } elseif ($line -match "\[FAIL\s*\]") {
        Write-Host $line -ForegroundColor Red
    } elseif ($line -match "\[BLOCKED\s*\]") {
        Write-Host $line -ForegroundColor Yellow
    } elseif ($line -match "\[WARNING\s*\]") {
        Write-Host $line -ForegroundColor Cyan
    } elseif ($line -match "\[NOT_APPLICABLE\]") {
        Write-Host $line -ForegroundColor DarkGray
    } elseif ($line -match "FINAL DECISION: READY") {
        Write-Host $line -ForegroundColor Green -BackgroundColor Black
    } elseif ($line -match "FINAL DECISION: BLOCKED") {
        Write-Host $line -ForegroundColor Yellow -BackgroundColor Black
    } elseif ($line -match "FINAL DECISION: FAIL") {
        Write-Host $line -ForegroundColor Red -BackgroundColor Black
    } elseif ($line -match "^={10,}") {
        Write-Host $line -ForegroundColor Blue
    } elseif ($line -match "^\[ .* \]$") {
        Write-Host $line -ForegroundColor Magenta
    } else {
        Write-Host $line
    }
}

if ($Stderr) {
    Write-Warning $Stderr
}

exit $ExitCode
