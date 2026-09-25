[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$GhidraHeadless,
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$ShortlistJson,
    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\ghidra')
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$DriverRoot=(Resolve-Path -LiteralPath $DriverRoot).Path
$GhidraHeadless=(Resolve-Path -LiteralPath $GhidraHeadless).Path
$ShortlistJson=(Resolve-Path -LiteralPath $ShortlistJson).Path
$OutputRoot=[IO.Path]::GetFullPath($OutputRoot)
$projectRoot=Join-Path $OutputRoot 'projects';$resultsRoot=Join-Path $OutputRoot 'results'
New-Item -ItemType Directory -Force -Path $projectRoot,$resultsRoot | Out-Null
$scriptPath=Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Export-GhidraExternalSymbols.py'
if(-not(Test-Path -LiteralPath $scriptPath -PathType Leaf)){throw "Missing Ghidra post-script: $scriptPath"}
$shortlist=@(Get-Content -LiteralPath $ShortlistJson -Raw | ConvertFrom-Json)
if($shortlist.Count -eq 0){throw 'Shortlist is empty. Generate ghidra-shortlist.json from render_backlog.py first.'}
if($shortlist.Count -gt 15){throw "Refusing more than 15 Ghidra targets; supplied $($shortlist.Count)."}
function Get-RelativePathHash([string]$Value){
    $sha=[Security.Cryptography.SHA256]::Create();try{$hash=$sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value));return ([BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant().Substring(0,16))}finally{$sha.Dispose()}
}
foreach($relative in $shortlist){
    $candidate=[IO.Path]::GetFullPath((Join-Path $DriverRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
    $prefix=$DriverRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar
    if(-not $candidate.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw "Shortlist path escapes DriverRoot: $relative"}
    if(-not(Test-Path -LiteralPath $candidate -PathType Leaf)){throw "Shortlist target missing: $relative"}
    if([IO.Path]::GetExtension($candidate).ToLowerInvariant() -notin @('.sys','.dll','.exe')){throw "Shortlist target is not PE-shaped: $relative"}
    $safe=(($candidate | Split-Path -Leaf) -replace '[^A-Za-z0-9_.-]','_')+'_'+(Get-RelativePathHash $relative)
    $projectName="gfyms_$safe";$projectDir=Join-Path $projectRoot $projectName;$resultFile=Join-Path $resultsRoot ($safe+'.json')
    New-Item -ItemType Directory -Force -Path $projectDir | Out-Null
    $ghidraArgs=@($projectDir,$projectName,'-scriptPath',(Split-Path -Parent $scriptPath),'-import',$candidate,'-analysisTimeoutPerFile','300','-postScript','Export-GhidraExternalSymbols.py',$resultFile)
    Write-Host "Analyzing $relative"
    & $GhidraHeadless @ghidraArgs 2>&1 | Tee-Object -FilePath (Join-Path $resultsRoot ($safe+'.log'))
    if($LASTEXITCODE -ne 0){throw "Ghidra failed for $relative with exit code $LASTEXITCODE"}
    [ordered]@{path=$relative;sha256=(Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant();project=$projectDir;result=$resultFile} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsRoot ($safe+'.manifest.json')) -Encoding utf8
}
Write-Host "Ghidra shortlist inventory complete: $($shortlist.Count) binaries analyzed. Projects were retained."
