[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $SignTool,
    [Parameter(Mandatory = $true)] [string] $Catalog,
    [Parameter(Mandatory = $true)] [string] $Inf
)

$ErrorActionPreference = 'Stop'
foreach ($item in @($SignTool, $Catalog, $Inf)) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "Missing file: $item" }
}

& $SignTool verify /kp $Catalog
if ($LASTEXITCODE -ne 0) { throw "Catalog kernel-policy verification failed: $LASTEXITCODE" }

& $SignTool verify /kp /c $Catalog $Inf
if ($LASTEXITCODE -ne 0) { throw "INF catalog coverage verification failed: $LASTEXITCODE" }

Write-Host 'Driver package signature verification completed. No package was installed.'
