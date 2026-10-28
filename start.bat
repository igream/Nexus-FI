@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
title Nexus FI — Servidor Web y Asistente RAG
color 0B

echo ========================================================================
echo        Nexus FI — Servidor Web y Asistente Virtual Inteligente
echo             Facultad de Ingeniería · UAEMéx (Equipo 404)
echo ========================================================================
echo.

set "PYTHON_CMD="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    py -3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3"
    ) else (
        python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=python"
        )
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] No se detectó un entorno virtual ni una instalación de Python válida.
    echo Por favor ejecuta primero 'setup.bat' para configurar el entorno automáticamente.
    echo.
    pause
    exit /b 1
)

echo Iniciando servidor web de Nexus FI...
echo Abriendo navegador en http://127.0.0.1:8000/
start "" http://127.0.0.1:8000/

echo.
echo ========================================================================
echo Presiona Ctrl+C en esta consola para detener el servidor web.
echo ========================================================================
echo.

if "%PYTHON_CMD%"=="py -3" (
    py -3 main.py --serve
) else (
    "%PYTHON_CMD%" main.py --serve
)

pause
