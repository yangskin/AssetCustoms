<#
.SYNOPSIS
    AssetCustoms dependency installer - deploys Python packages to Content/Python/.

.DESCRIPTION
    UE automatically adds plugin Content/Python/ to sys.path on startup.
    This script installs third-party packages (e.g. PIL/) directly into
    Content/Python/ so UE Python can import them without any path hacks.

    Strategy:
    1. Prefer offline install from vendor/ (fast, no network required)
    2. Fall back to online pip install

.PARAMETER PythonExe
    Python interpreter path. Defaults to UE bundled Python.

.PARAMETER Online
    Force online install (skip vendor/).

.PARAMETER Clean
    Remove installed packages before reinstalling.

.EXAMPLE
    .\deploy.ps1
    .\deploy.ps1 -PythonExe "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
    .\deploy.ps1 -Online
    .\deploy.ps1 -Clean
#>
param(
    [string]$PythonExe = "",
    [switch]$Online,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# ============================================================
# Path definitions
# ============================================================
$pluginRoot  = (Resolve-Path $PSScriptRoot).Path
$contentPy   = Join-Path $pluginRoot "Content\Python"
$targetDir   = $contentPy   # packages go directly into Content/Python/
$vendorDir   = Join-Path $pluginRoot "vendor"
$reqFile     = Join-Path $pluginRoot "requirements.txt"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AssetCustoms Dependency Installer"      -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Plugin:       $pluginRoot"
Write-Host "  Target:       $targetDir"
Write-Host "  Vendor:       $vendorDir"
Write-Host "  Requirements: $reqFile"
Write-Host ""

# ============================================================
# 自动检测 UE Python
# ============================================================
if (-not $PythonExe) {
    # 尝试从项目的 .uproject 反推 UE 引擎路径
    $uprojectFiles = Get-ChildItem -Path (Split-Path $pluginRoot -Parent | Split-Path -Parent) -Filter "*.uproject" -ErrorAction SilentlyContinue
    $enginePython = ""

    # 常见 UE 安装路径
    $enginePaths = @(
        "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe",
        "C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\ThirdParty\Python3\Win64\python.exe",
        "C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
    )
    foreach ($ep in $enginePaths) {
        if (Test-Path $ep) {
            $enginePython = $ep
            break
        }
    }

    if ($enginePython) {
        $PythonExe = $enginePython
        Write-Host "  Auto-detected UE Python: $PythonExe" -ForegroundColor Green
    } else {
        # 回退到系统 Python
        $PythonExe = "python"
        Write-Host "  Using system Python (UE Python not found)" -ForegroundColor Yellow
    }
}

# 验证 Python 可用
try {
    $pyVer = & $PythonExe --version 2>&1
    Write-Host "  Python version: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found at $PythonExe" -ForegroundColor Red
    exit 1
}

# ============================================================
# Clean (optional)
# ============================================================
# Track managed package directories for clean operation
$managedPackages = @(
    "PIL", "pillow-*.dist-info",
    "PySide6", "PySide6_Essentials*.dist-info",
    "shiboken6", "shiboken6*.dist-info",
    "psd_tools", "psd_tools-*.dist-info",
    "attrs", "attrs-*.dist-info",
    "typing_extensions*",
    "numpy", "numpy-*.dist-info", "numpy.libs"
)

if ($Clean) {
    Write-Host ""
    Write-Host "Cleaning installed packages..." -ForegroundColor Yellow
    foreach ($pattern in $managedPackages) {
        $matches = Get-ChildItem -Path $targetDir -Filter $pattern -Directory -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            Remove-Item -Recurse -Force $m.FullName
            Write-Host "  Removed: $($m.Name)"
        }
    }
    # Also clean legacy Lib/site-packages if present
    $legacyLib = Join-Path $contentPy "Lib"
    if (Test-Path $legacyLib) {
        Remove-Item -Recurse -Force $legacyLib
        Write-Host "  Removed legacy: Lib/"
    }
}

# ============================================================
# Ensure target directory exists
# ============================================================
if (!(Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Write-Host "  Created: $targetDir"
}

# ============================================================
# Check requirements.txt
# ============================================================
if (!(Test-Path $reqFile)) {
    Write-Host "ERROR: requirements.txt not found at $reqFile" -ForegroundColor Red
    exit 1
}

# ============================================================
# Install dependencies
# ============================================================
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Cyan
$installed = $false

# --- 方案 A: 离线安装 ---
if (!$Online -and (Test-Path $vendorDir)) {
    $wheels = Get-ChildItem -Path $vendorDir -Filter "*.whl" -ErrorAction SilentlyContinue
    if ($wheels.Count -gt 0) {
        Write-Host "  [Offline] Found $($wheels.Count) wheel(s) in vendor/" -ForegroundColor DarkGray
        Write-Host "  [Offline] Installing from vendor/..." -ForegroundColor DarkGray

        # Install wheel files directly (bypass requirements.txt to avoid old pip encoding issues)
        $wheelPaths = $wheels | ForEach-Object { $_.FullName }
        $offlineArgs = @("-m", "pip", "install") + $wheelPaths + @("--target", $targetDir, "--upgrade", "--no-deps")

        $proc = Start-Process -FilePath $PythonExe -ArgumentList $offlineArgs -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -eq 0) {
            $installed = $true
            Write-Host "  [Offline] Install succeeded!" -ForegroundColor Green
        } else {
            Write-Host "  [Offline] Install failed (exit=$($proc.ExitCode)), trying online..." -ForegroundColor Yellow
        }
    }
}

# --- 方案 B: 在线安装 ---
if (-not $installed) {
    Write-Host "  [Online] Installing from PyPI..." -ForegroundColor DarkGray

    $onlineArgs = @(
        "-m", "pip", "install",
        "-r", $reqFile,
        "--target", $targetDir,
        "--upgrade",
        "--retries", "3",
        "--timeout", "60"
    )

    $proc = Start-Process -FilePath $PythonExe -ArgumentList $onlineArgs -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -eq 0) {
        $installed = $true
        Write-Host "  [Online] Install succeeded!" -ForegroundColor Green
    } else {
        Write-Host "  [Online] Install failed (exit=$($proc.ExitCode))." -ForegroundColor Red
    }
}

if (-not $installed) {
    Write-Host ""
    Write-Host "ERROR: Failed to install dependencies." -ForegroundColor Red
    Write-Host "  Try manually: pip install -r requirements.txt --target `"$targetDir`"" -ForegroundColor Yellow
    exit 1
}

# ============================================================
# Verify installation
# ============================================================
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Cyan

$verifyCode = @"
import sys
sys.path.insert(0, r'$($targetDir -replace "\\", "\\")')
ok = True
try:
    from PIL import Image
    print(f'Pillow OK: version={Image.__version__}')
except ImportError as e:
    print(f'Pillow FAILED: {e}')
    ok = False
try:
    from PySide6 import QtCore, QtWidgets
    print(f'PySide6 OK: version={QtCore.qVersion()}')
except ImportError as e:
    print(f'PySide6 FAILED: {e}')
    ok = False
try:
    from psd_tools import PSDImage
    print(f'psd-tools OK: version={PSDImage.__module__}')
except ImportError as e:
    print(f'psd-tools FAILED: {e}')
    ok = False
sys.exit(0 if ok else 1)
"@

$verifyResult = & $PythonExe -c $verifyCode 2>&1
Write-Host "  $verifyResult"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Verification failed." -ForegroundColor Red
    exit 1
}

# ============================================================
# Done
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Installation complete!"                  -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Packages installed to: $targetDir" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host "    1. Restart Unreal Editor to load new packages"
Write-Host "    2. In UE Python console: from PIL import Image"
Write-Host "    3. In UE Python console: from PySide6 import QtWidgets"
Write-Host "    4. In UE Python console: from psd_tools import PSDImage"
Write-Host ""
