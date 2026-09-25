[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,

    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\\imports')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DriverRoot = (Resolve-Path -LiteralPath $DriverRoot).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

function Resolve-Tool([string[]]$Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $cmd) { return $cmd.Source }
    }
    return $null
}

$llvmReadobj = Resolve-Tool @('llvm-readobj.exe', 'llvm-readobj')
$dumpbin = Resolve-Tool @('dumpbin.exe', 'dumpbin')
if ($null -eq $llvmReadobj -and $null -eq $dumpbin) {
    throw 'No PE inspection tool found. Install LLVM (llvm-readobj) or Visual Studio/Windows SDK (dumpbin).'
}

$targets = @(Get-ChildItem -LiteralPath $DriverRoot -Recurse -File |
    Where-Object { $_.Extension -in @('.sys', '.dll', '.exe') } |
    Sort-Object FullName)

$records = foreach ($target in $targets) {
    $safeName = ($target.BaseName -replace '[^A-Za-z0-9_.-]', '_')
    $outPath = Join-Path $OutputRoot ($safeName + '.imports.txt')
    $relative = [IO.Path]::GetRelativePath($DriverRoot, $target.FullName) -replace '\\','/'

    if ($null -ne $llvmReadobj) {
        & $llvmReadobj '--coff-imports' $target.FullName 2>&1 |
            Set-Content -LiteralPath $outPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            throw "llvm-readobj failed for $($target.FullName) with exit code $LASTEXITCODE"
        }
        $tool = 'llvm-readobj'
    } else {
        & $dumpbin '/imports' $target.FullName 2>&1 |
            Set-Content -LiteralPath $outPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            throw "dumpbin failed for $($target.FullName) with exit code $LASTEXITCODE"
        }
        $tool = 'dumpbin'
    }

    [ordered]@{
        path = $relative
        tool = $tool
        output = [IO.Path]::GetFileName($outPath)
        sha256 = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$records | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $OutputRoot 'imports-manifest.json') -Encoding utf8

Write-Host "Extracted imports for $($targets.Count) PE images using $(if ($null -ne $llvmReadobj) { 'llvm-readobj' } else { 'dumpbin' })."
