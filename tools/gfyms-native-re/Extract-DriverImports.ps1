[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,
    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research\imports')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DriverRoot=(Resolve-Path -LiteralPath $DriverRoot).Path
$OutputRoot=[IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
function Resolve-Tool([string[]]$Names){foreach($name in $Names){$cmd=Get-Command $name -ErrorAction SilentlyContinue;if($null -ne $cmd){return $cmd.Source}};return $null}
function Test-LfsPointer([string]$Path){try{return ((Get-Content -LiteralPath $Path -TotalCount 1 -ErrorAction Stop) -like 'version https://git-lfs.github.com/spec/v1*')}catch{return $false}}
function Get-RelativePathHash([string]$Value){
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$hash=$sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value));return ([BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant().Substring(0,16))}finally{$sha.Dispose()}
}
$llvmReadobj=Resolve-Tool @('llvm-readobj.exe','llvm-readobj');$dumpbin=Resolve-Tool @('dumpbin.exe','dumpbin')
if($null -eq $llvmReadobj -and $null -eq $dumpbin){throw 'No PE inspection tool found. Install LLVM (llvm-readobj) or Visual Studio/Windows SDK (dumpbin).'}
$targets=@(Get-ChildItem -LiteralPath $DriverRoot -Recurse -File | Where-Object {$_.Extension.ToLowerInvariant() -in @('.sys','.dll','.exe')} | Sort-Object FullName)
$records=foreach($target in $targets){
    $relative=[IO.Path]::GetRelativePath($DriverRoot,$target.FullName)-replace '\','/'
    $safeName=(($target.BaseName -replace '[^A-Za-z0-9_.-]','_')+'_'+(Get-RelativePathHash $relative))
    $outPath=Join-Path $OutputRoot ($safeName+'.imports.txt')
    $hash=(Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if(Test-LfsPointer $target.FullName){
        "LFS POINTER: restore with git lfs pull before PE import extraction. Path: $relative. SHA256: $hash" | Set-Content -LiteralPath $outPath -Encoding utf8
        [ordered]@{path=$relative;tool=$null;output=[IO.Path]::GetFileName($outPath);sha256=$hash;lfs_pointer=$true;status='skipped-lfs-pointer'}
        continue
    }
    if($null -ne $llvmReadobj){
        & $llvmReadobj '--coff-imports' $target.FullName 2>&1 | Set-Content -LiteralPath $outPath -Encoding utf8
        if($LASTEXITCODE -ne 0){throw "llvm-readobj failed for $relative with exit code $LASTEXITCODE"};$tool='llvm-readobj'
    }else{
        & $dumpbin '/imports' $target.FullName 2>&1 | Set-Content -LiteralPath $outPath -Encoding utf8
        if($LASTEXITCODE -ne 0){throw "dumpbin failed for $relative with exit code $LASTEXITCODE"};$tool='dumpbin'
    }
    [ordered]@{path=$relative;tool=$tool;output=[IO.Path]::GetFileName($outPath);sha256=$hash;lfs_pointer=$false;status='ok'}
}
$records | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputRoot 'imports-manifest.json') -Encoding utf8
Write-Host "Extracted imports for $($targets.Count) PE images using $(if($null -ne $llvmReadobj){'llvm-readobj'}else{'dumpbin'})."
