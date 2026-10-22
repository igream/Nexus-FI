@echo off
title Diagnostico y Auditoria de API Gemini - PotroBot UAEMex
color 0B

echo ========================================================
echo    POTROBOT UAEMex - PANEL DE DIAGNOSTICO DE API
echo ========================================================
echo.

set PYTHON_CMD=python
if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Python\bin\python.exe"
)

echo Usando ejecutable: %PYTHON_CMD%
echo.

echo [PASO 1/2] Ejecutando Auditoria de Seguridad de Credenciales...
"%PYTHON_CMD%" "%~dp0auditor_seguridad_api.py"

echo.
echo --------------------------------------------------------
echo.

echo [PASO 2/2] Evaluando Conexion en Vivo con Google Gemini API...
"%PYTHON_CMD%" "%~dp0probar_conexion_api.py"

echo.
echo ========================================================
echo Diagnostico finalizado. Presiona cualquier tecla para salir.
pause >nul
