[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Solution,
    [Parameter(Mandatory = $true)] [string] $MSBuild,
    [ValidateSet('Debug', 'Release')] [string] $Configuration = 'Release',
    [ValidateSet('x64', 'ARM64', 'Win32')] [string] $Platform = 'x64',
    [string] $InfVerif,
    [string] $Inf,
    [string] $Inf2Cat,
    [string] $DriverPackageDirectory,
    [string] $OsList
)

$ErrorActionPreference = 'Stop'

function Require-File([string] $Path, [string] $Name) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Name was not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

$solutionPath = Require-File $Solution 'Solution'
$msbuildPath = Require-File $MSBuild 'MSBuild'

& $msbuildPath $solutionPath /m "/p:Configuration=$Configuration" "/p:Platform=$Platform"
if ($LASTEXITCODE -ne 0) { throw "MSBuild failed with exit code $LASTEXITCODE" }

if ($InfVerif -or $Inf) {
    if (-not ($InfVerif -and $Inf)) { throw 'InfVerif and Inf must be provided together' }
    $infverifPath = Require-File $InfVerif 'InfVerif'
    $infPath = Require-File $Inf 'INF'
    & $infverifPath $infPath
    if ($LASTEXITCODE -ne 0) { throw "InfVerif failed with exit code $LASTEXITCODE" }
}

if ($Inf2Cat -or $DriverPackageDirectory -or $OsList) {
    if (-not ($Inf2Cat -and $DriverPackageDirectory -and $OsList)) {
        throw 'Inf2Cat, DriverPackageDirectory, and OsList must be provided together'
    }
    $inf2catPath = Require-File $Inf2Cat 'Inf2Cat'
    if (-not (Test-Path -LiteralPath $DriverPackageDirectory -PathType Container)) {
        throw "Driver package directory was not found: $DriverPackageDirectory"
    }
    & $inf2catPath "/driver:$DriverPackageDirectory" "/os:$OsList"
    if ($LASTEXITCODE -ne 0) { throw "Inf2Cat failed with exit code $LASTEXITCODE" }
}

Write-Host 'Build and requested validation completed. No signing or deployment was performed.'
