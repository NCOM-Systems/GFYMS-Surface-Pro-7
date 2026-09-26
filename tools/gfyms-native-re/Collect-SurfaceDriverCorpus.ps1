[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$DriverRoot,
    [string]$OutputRoot = (Join-Path $PWD 'gfyms-driver-research'),
    [switch]$IncludeLiveSystem
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DriverRoot = (Resolve-Path -LiteralPath $DriverRoot).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
function Test-LfsPointer([string]$Path) {
    try { return ((Get-Content -LiteralPath $Path -TotalCount 1 -ErrorAction Stop) -like 'version https://git-lfs.github.com/spec/v1*') }
    catch { return $false }
}
function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-SignerStatus([string]$Path) {
    try {
        $sig = Get-AuthenticodeSignature -LiteralPath $Path
        [ordered]@{ status=[string]$sig.Status; status_message=[string]$sig.StatusMessage;
            signer=if ($null -ne $sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { $null };
            thumbprint=if ($null -ne $sig.SignerCertificate) { $sig.SignerCertificate.Thumbprint } else { $null } }
    } catch { [ordered]@{status='Error';status_message=$_.Exception.Message;signer=$null;thumbprint=$null} }
}
function Get-TextDirectives([string]$Path) {
    $patterns=@('^\s*Signature\s*=','^\s*Class\s*=','^\s*ClassGuid\s*=','^\s*Provider\s*=',
        '^\s*DriverVer\s*=','^\s*CatalogFile','^\s*Manufacturer\s*=','^\s*AddService\s*=',
        '^\s*CopyFiles\s*=','^\s*Needs\s*=','^\s*Include\s*=')
    $hits=New-Object System.Collections.Generic.List[string]
    foreach($line in Get-Content -LiteralPath $Path -ErrorAction Stop){ foreach($pattern in $patterns){ if($line -match $pattern){$hits.Add($line.Trim());break} } }
    @($hits)
}
$files=@(Get-ChildItem -LiteralPath $DriverRoot -Recurse -File | Where-Object {$_.Extension.ToLowerInvariant() -in @('.sys','.dll','.exe','.inf','.cat')} | Sort-Object FullName)
$binaries=foreach($file in $files | Where-Object {$_.Extension.ToLowerInvariant() -in @('.sys','.dll','.exe')}){
    $isLfs=Test-LfsPointer $file.FullName
    [ordered]@{path=[IO.Path]::GetRelativePath($DriverRoot,$file.FullName)-replace '\','/';extension=$file.Extension.ToLowerInvariant();size=$file.Length;sha256=Get-Sha256 $file.FullName;lfs_pointer=$isLfs;signer=if($isLfs){$null}else{Get-SignerStatus $file.FullName}}
}
$infs=foreach($file in $files | Where-Object {$_.Extension.ToLowerInvariant() -eq '.inf'}){
    [ordered]@{path=[IO.Path]::GetRelativePath($DriverRoot,$file.FullName)-replace '\','/';sha256=Get-Sha256 $file.FullName;directives=Get-TextDirectives $file.FullName}
}
$catalogs=foreach($file in $files | Where-Object {$_.Extension.ToLowerInvariant() -eq '.cat'}){
    [ordered]@{path=[IO.Path]::GetRelativePath($DriverRoot,$file.FullName)-replace '\','/';sha256=Get-Sha256 $file.FullName;signer=Get-SignerStatus $file.FullName}
}
$pnp=@();$services=@()
if($IncludeLiveSystem){
    try{$pnp=@(Get-CimInstance Win32_PnPSignedDriver | Select-Object DeviceName,DeviceID,DriverVersion,DriverProviderName,InfName,Manufacturer | Sort-Object DeviceID)}catch{$pnp=@([ordered]@{error=$_.Exception.Message})}
    try{$services=@(Get-CimInstance Win32_SystemDriver | Where-Object {$_.PathName -match '\.sys(?:[" ]|$)'} | Select-Object Name,DisplayName,State,StartMode,ServiceType,PathName | Sort-Object Name)}catch{$services=@([ordered]@{error=$_.Exception.Message})}
}
$manifest=[ordered]@{
    schema='gfyms.native-driver-re.v2';generated_utc=[DateTime]::UtcNow.ToString('o')
    host=[ordered]@{computer=$env:COMPUTERNAME;os=[Environment]::OSVersion.VersionString;architecture=[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()}
    source=[ordered]@{root=$DriverRoot;file_count=$files.Count;live_system_included=[bool]$IncludeLiveSystem}
    binaries=@($binaries);infs=@($infs);catalogs=@($catalogs);installed_pnp=$pnp;kernel_services=$services
}
$manifestPath=Join-Path $OutputRoot 'manifest.json'
$manifest | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$reportPath=Join-Path $OutputRoot 'REPORT.txt'
@"
GFYMS Native Driver RE
======================
Generated: $($manifest.generated_utc)
Source:   $DriverRoot
Files:
  Binaries : $(@($binaries).Count)
  INFs     : $(@($infs).Count)
  CATs     : $(@($catalogs).Count)
  PnP      : $($pnp.Count)
  Services : $($services.Count)
  Live PnP/services included: $([bool]$IncludeLiveSystem)
"@ | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Host 'GFYMS native driver corpus collected.'
Write-Host "Manifest: $manifestPath"
Write-Host "Report:   $reportPath"
