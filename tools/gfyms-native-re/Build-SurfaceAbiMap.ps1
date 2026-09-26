[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,
    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\abi-map')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DriverRoot = (Resolve-Path -LiteralPath $DriverRoot).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirements = Join-Path $toolDir 'requirements.txt'
$python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command python.exe -ErrorAction SilentlyContinue }
if ($null -eq $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if ($null -eq $python) { throw 'Python 3 is required. Install Python and ensure py.exe or python.exe is on PATH.' }
$tablesDir = Join-Path $DriverRoot 'tables'
$directoryTable = Join-Path $tablesDir 'Directory.csv'
if (-not (Test-Path -LiteralPath $directoryTable -PathType Leaf)) {
    Write-Warning "MSI Directory.csv is missing under '$tablesDir'. MSI File -> on-disk PE joins will be incomplete."
}
$lfsCount = 0
foreach ($file in Get-ChildItem -LiteralPath $DriverRoot -Recurse -File | Where-Object { $_.Extension.ToLowerInvariant() -in @('.sys','.dll','.exe') }) {
    try {
        if ((Get-Content -LiteralPath $file.FullName -TotalCount 1 -ErrorAction Stop) -like 'version https://git-lfs.github.com/spec/v1*') { $lfsCount++ }
    } catch { }
}
if ($lfsCount -gt 0) { Write-Warning "Detected $lfsCount Git-LFS pointer PE image(s). Run 'git lfs pull' before relying on ABI results." }
& $python.Source -m pip show pefile *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing the local ABI-map dependency set...'
    & $python.Source -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install ABI-map dependencies.' }
}
$builder = Join-Path $toolDir 'build_abi_map.py'
$renderer = Join-Path $toolDir 'render_backlog.py'
$arguments = @($builder,$DriverRoot,'--output',(Join-Path $OutputRoot 'abi-map.json'),'--markdown',(Join-Path $OutputRoot 'abi-map.md'),'--schema','v2')
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "ABI map generation failed with exit code $LASTEXITCODE" }
& $python.Source $renderer (Join-Path $OutputRoot 'abi-map.json') '--output-csv' (Join-Path $OutputRoot 'backlog.csv') '--shortlist' (Join-Path $OutputRoot 'ghidra-shortlist.json')
if ($LASTEXITCODE -ne 0) { throw "Backlog rendering failed with exit code $LASTEXITCODE" }
Write-Host 'ABI map v2 generation complete.'
Write-Host "Output: $OutputRoot"
