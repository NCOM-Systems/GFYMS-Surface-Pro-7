[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,

    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\abi-map')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirements = Join-Path $toolDir 'requirements.txt'
$python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -eq $python) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
}
if ($null -eq $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if ($null -eq $python) {
    throw 'Python 3 is required. Install Python and ensure py.exe or python.exe is on PATH.'
}

& $python.Source -m pip show pefile *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing the local ABI-map dependency set...'
    & $python.Source -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install ABI-map dependencies.'
    }
}

$builder = Join-Path $toolDir 'build_abi_map.py'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$arguments = @(
    $builder,
    $DriverRoot,
    '--output', (Join-Path $OutputRoot 'abi-map.json'),
    '--markdown', (Join-Path $OutputRoot 'abi-map.md')
)
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "ABI map generation failed with exit code $LASTEXITCODE"
}
