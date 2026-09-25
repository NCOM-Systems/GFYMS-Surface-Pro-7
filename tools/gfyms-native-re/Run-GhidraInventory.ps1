[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$GhidraHeadless,

    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\\ghidra')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DriverRoot = (Resolve-Path -LiteralPath $DriverRoot).Path
$GhidraHeadless = (Resolve-Path -LiteralPath $GhidraHeadless).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)

$projectRoot = Join-Path $OutputRoot 'projects'
$resultsRoot = Join-Path $OutputRoot 'results'
New-Item -ItemType Directory -Force -Path $projectRoot, $resultsRoot | Out-Null

$targets = @(Get-ChildItem -LiteralPath $DriverRoot -Recurse -File |
    Where-Object { $_.Extension -in @('.sys', '.dll', '.exe') } |
    Sort-Object FullName)

foreach ($target in $targets) {
    $safeName = ($target.BaseName -replace '[^A-Za-z0-9_.-]', '_')
    $projectName = "gfyms_$safeName"
    $projectDir = Join-Path $projectRoot $projectName
    New-Item -ItemType Directory -Force -Path $projectDir | Out-Null

    $ghidraArgs = @(
        $projectDir,
        $projectName,
        '-import', $target.FullName,
        '-analysisTimeoutPerFile', '300',
        '-deleteProject'
    )

    Write-Host "Analyzing $($target.FullName)"
    & $GhidraHeadless @ghidraArgs 2>&1 |
        Tee-Object -FilePath (Join-Path $resultsRoot "$safeName.log")

    if ($LASTEXITCODE -ne 0) {
        throw "Ghidra failed for $($target.FullName) with exit code $LASTEXITCODE"
    }
}

Write-Host "Ghidra inventory complete: $($targets.Count) binaries analyzed."
