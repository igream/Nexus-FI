@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Nexus FI — Detener servidores

echo ========================================================================
echo        Nexus FI — Detener todos los servidores en ejecución
echo ========================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\detener_servidores.ps1" %*

echo.
pause
