@echo off
chcp 65001 >nul 2>&1
title AssetCustoms Dependency Installer

:: ============================================================
:: deploy.bat — Windows 双击引导脚本
:: 功能：以 Bypass 执行策略调用 deploy.ps1，绕过系统限制
:: 用法：双击运行，或命令行执行 deploy.bat [参数]
::   deploy.bat              — 默认离线安装
::   deploy.bat -Online      — 强制在线安装
::   deploy.bat -Clean       — 清理后重新安装
:: ============================================================

echo ========================================
echo  AssetCustoms Deploy Launcher
echo ========================================
echo.

:: 定位脚本目录（支持从任意位置调用）
set "SCRIPT_DIR=%~dp0"

:: 检查 deploy.ps1 存在
if not exist "%SCRIPT_DIR%deploy.ps1" (
    echo [ERROR] deploy.ps1 not found in %SCRIPT_DIR%
    echo         Please ensure this file is in the AssetCustoms plugin root.
    pause
    exit /b 1
)

:: 尝试查找 PowerShell
where powershell >nul 2>&1
if %errorlevel% equ 0 (
    set "PS_EXE=powershell"
) else (
    where pwsh >nul 2>&1
    if %errorlevel% equ 0 (
        set "PS_EXE=pwsh"
    ) else (
        echo [ERROR] PowerShell not found on this system.
        echo         Please install PowerShell or run deploy.ps1 manually.
        pause
        exit /b 1
    )
)

echo Using: %PS_EXE%
echo Script: %SCRIPT_DIR%deploy.ps1
echo Args:   %*
echo.

:: 使用 -ExecutionPolicy Bypass 运行，无需修改系统策略
%PS_EXE% -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%deploy.ps1" %*

:: 保留退出码
set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% equ 0 (
    echo [OK] Deploy completed successfully.
) else (
    echo [FAIL] Deploy failed with exit code %EXIT_CODE%.
)

echo.
echo Press any key to close...
pause >nul
exit /b %EXIT_CODE%
