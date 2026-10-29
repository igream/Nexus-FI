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

:: ---------------------------------------------------------------------------
:: 1. Detectar Python (entorno virtual .venv o instalación del sistema)
:: ---------------------------------------------------------------------------
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

if "%PYTHON_CMD%"=="py -3" (
    set "PYRUN=py -3"
) else (
    set PYRUN="%PYTHON_CMD%"
)

:: IP de este equipo en la red y si pertenece a las subredes de la FI
set "LAN_IP=127.0.0.1"
set "IN_FI=0"
%PYRUN% scripts\lan_info.py > "%TEMP%\nexusfi_lan.txt" 2>nul
set /p LAN_LINE=<"%TEMP%\nexusfi_lan.txt"
del "%TEMP%\nexusfi_lan.txt" >nul 2>&1
for /f "tokens=1,2 delims=|" %%a in ("%LAN_LINE%") do (
    set "LAN_IP=%%a"
    set "IN_FI=%%b"
)

:: ---------------------------------------------------------------------------
:: 2. Elegir el modo (se omite si se pasan argumentos: start.bat --fi / --dev)
:: ---------------------------------------------------------------------------
if not "%~1"=="" (
    set "SERVE_ARGS=%*"
    set "OPEN_URL=http://%LAN_IP%:8000/"
    echo %* | find /i "--fi" >nul || set "OPEN_URL=http://127.0.0.1:8000/"
    goto :run
)

echo  ¿Cómo quieres iniciar Nexus FI?
echo.
echo    [1] Desarrollo - solo este equipo
echo        Sin filtro de subredes ni límite de consultas. http://127.0.0.1:8000
echo.
echo    [2] Desarrollo - en la red
echo        Igual que 1, pero accesible desde celulares u otros equipos.
echo        http://%LAN_IP%:8000
echo.
echo    [3] Modo FI - prueba final / demo
echo        Filtro de subredes FI (WBS 1.3.5) y límite de consultas (WBS 1.4.2) activos.
echo        http://%LAN_IP%:8000
echo.
choice /c 123 /n /t 30 /d 1 /m "  Elige una opción [1-3] (se usará 1 en 30 segundos): "
set "OPCION=%errorlevel%"
echo.

if "%OPCION%"=="3" (
    set "SERVE_ARGS=--fi"
    set "OPEN_URL=http://%LAN_IP%:8000/"
    if not "%IN_FI%"=="1" (
        echo  [AVISO] La IP de este equipo ^(%LAN_IP%^) no está en las subredes de la FI.
        echo          El chat y los tableros responderán 403 ^(acceso denegado^).
        echo          Conéctate a la red de la Facultad o usa la opción 1 o 2 para probar.
        echo.
    )
) else if "%OPCION%"=="2" (
    set "SERVE_ARGS=--dev --host 0.0.0.0"
    set "OPEN_URL=http://%LAN_IP%:8000/"
) else (
    set "SERVE_ARGS=--dev"
    set "OPEN_URL=http://127.0.0.1:8000/"
)

:run
:: ---------------------------------------------------------------------------
:: 3. Abrir el navegador cuando el servidor haya arrancado e iniciarlo
:: ---------------------------------------------------------------------------
echo Iniciando servidor web de Nexus FI...
echo El navegador se abrirá en %OPEN_URL%
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 6; Start-Process '%OPEN_URL%'"

echo.
echo ========================================================================
echo Presiona Ctrl+C en esta consola para detener el servidor web.
echo ========================================================================
echo.

%PYRUN% main.py --serve %SERVE_ARGS%

pause
