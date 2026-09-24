#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter()]
    [string]$MsiPath = 'C:\Users\Offic\Downloads\SurfacePro7_Win11_22621_25.090.3489.0.msi',

    [Parameter()]
    [switch]$OpenMsiPreview
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$artifactsDir = Join-Path $repoRoot 'artifacts'
$venvDir = Join-Path $repoRoot '.venv-pymsi'

$baseName = [System.IO.Path]::GetFileNameWithoutExtension($MsiPath)
$extractDir = Join-Path $artifactsDir ($baseName + '-extracted')
$zipPath = Join-Path $artifactsDir ($baseName + '-extracted.zip')
$manifestPath = Join-Path $artifactsDir ($baseName + '-extracted.sha256.txt')

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,

        [Parameter()]
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed with exit code {0}: {1} {2}" -f $LASTEXITCODE, $FilePath, ($Arguments -join ' '))
    }
}

function Get-PythonLauncher {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        return $pyCommand.Source
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Install Python 3.8+ and make the Python launcher available as 'py' or 'python'."
}

if (-not (Test-Path -LiteralPath $MsiPath -PathType Leaf)) {
    throw "MSI file not found: $MsiPath"
}

if ($OpenMsiPreview) {
    Start-Process 'https://pymsi.readthedocs.io/en/latest/msi_viewer.html'
}

New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null

$sourceHash = Get-FileHash -LiteralPath $MsiPath -Algorithm SHA256
$sourceSize = (Get-Item -LiteralPath $MsiPath).Length

$python = Get-PythonLauncher

if (-not (Test-Path -LiteralPath $venvDir -PathType Container)) {
    Invoke-Checked -FilePath $python -Arguments @('-m', 'venv', $venvDir)
}

$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$pymsiExe = Join-Path $venvDir 'Scripts\pymsi.exe'

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "The Python virtual environment was created without its interpreter: $venvPython"
}

Write-Host 'Installing/updating pymsi from nightlark/pymsi main...' -ForegroundColor Cyan
Invoke-Checked -FilePath $venvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip')
Invoke-Checked -FilePath $venvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'git+https://github.com/nightlark/pymsi.git@main')

if (-not (Test-Path -LiteralPath $pymsiExe -PathType Leaf)) {
    throw "pymsi CLI was not installed where expected: $pymsiExe"
}

if (Test-Path -LiteralPath $extractDir) {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

if (Test-Path -LiteralPath $manifestPath) {
    Remove-Item -LiteralPath $manifestPath -Force
}

Write-Host 'Validating MSI...' -ForegroundColor Cyan
Invoke-Checked -FilePath $pymsiExe -Arguments @('test', $MsiPath)

Write-Host "Extracting MSI contents to $extractDir ..." -ForegroundColor Cyan
Invoke-Checked -FilePath $pymsiExe -Arguments @('extract', $MsiPath, $extractDir)

if (-not (Test-Path -LiteralPath $extractDir -PathType Container)) {
    throw "pymsi completed without creating the extraction directory: $extractDir"
}

Write-Host "Creating ZIP: $zipPath ..." -ForegroundColor Cyan
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $extractDir,
    $zipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
    throw "ZIP creation failed: $zipPath"
}

$zipHash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
$zipSize = (Get-Item -LiteralPath $zipPath).Length

@(
    "Source MSI: " + $MsiPath
    "Source MSI size: " + $sourceSize + " bytes"
    "Source MSI SHA-256: " + $sourceHash.Hash
    "Generated ZIP: " + $zipPath
    "Generated ZIP size: " + $zipSize + " bytes"
    "Generated ZIP SHA-256: " + $zipHash.Hash
    "Extraction tool: nightlark/pymsi"
    "Extraction source: https://github.com/nightlark/pymsi.git@main"
    "Preview: https://pymsi.readthedocs.io/en/latest/msi_viewer.html"
    "Generated: " + (Get-Date -Format o)
) | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Remove-Item -LiteralPath $extractDir -Recurse -Force

$gitRelativeZip = 'artifacts/' + [System.IO.Path]::GetFileName($zipPath)
$zipIsLarge = $zipSize -ge (90MB)

Push-Location $repoRoot
try {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCommand) {
        throw 'Git was not found. Install Git for Windows and re-run this script.'
    }

    if ($zipSize -ge (2GB)) {
        throw 'The generated ZIP is 2 GiB or larger. GitHub Free/Pro Git LFS has a 2 GiB per-file limit; use a GitHub Release or another binary store for this file.'
    }

    & $gitCommand.Source -C $repoRoot rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "This script must be run from a clone of pfn000/GFYMS-Surface-Pro-7."
    }

    if ($zipIsLarge) {
        $lfsCommand = Get-Command git-lfs -ErrorAction SilentlyContinue
        if (-not $lfsCommand) {
            throw 'The generated ZIP is at least 90 MiB, so Git LFS is required before pushing it. Install Git LFS and re-run this script.'
        }

        Invoke-Checked -FilePath $gitCommand.Source -Arguments @('lfs', 'install')
        Invoke-Checked -FilePath $gitCommand.Source -Arguments @('lfs', 'track', 'artifacts/*.zip')
    }

    Invoke-Checked -FilePath $gitCommand.Source -Arguments @('-C', $repoRoot, 'add', '--', $gitRelativeZip)
    Invoke-Checked -FilePath $gitCommand.Source -Arguments @('-C', $repoRoot, 'add', '--', 'artifacts/*.sha256.txt')

    if ($zipIsLarge -and (Test-Path -LiteralPath (Join-Path $repoRoot '.gitattributes'))) {
        Invoke-Checked -FilePath $gitCommand.Source -Arguments @('-C', $repoRoot, 'add', '--', '.gitattributes')
    }

    & $gitCommand.Source -C $repoRoot diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'No new Git changes to commit.' -ForegroundColor Yellow
        return
    }

    Invoke-Checked -FilePath $gitCommand.Source -Arguments @(
        '-C', $repoRoot,
        'commit',
        '-m', 'Extract Surface Pro 7 MSI with pymsi'
    )

    $branch = (& $gitCommand.Source -C $repoRoot branch --show-current).Trim()
    if ([string]::IsNullOrWhiteSpace($branch)) {
        throw 'Could not determine the current Git branch.'
    }

    Write-Host "Pushing branch '$branch' to origin..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $gitCommand.Source -Arguments @('-C', $repoRoot, 'push', '--set-upstream', 'origin', $branch)

    Write-Host ''
    Write-Host 'Done.' -ForegroundColor Green
    Write-Host "ZIP:      $zipPath"
    Write-Host "Manifest: $manifestPath"
}
finally {
    Pop-Location
}
