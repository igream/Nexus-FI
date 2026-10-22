@echo off
chcp 65001 >nul
title Nexus FI — Servidor Web y Asistente RAG
color 0B

echo ========================================================================
echo        Nexus FI — Servidor Web y Asistente Virtual Inteligente
echo             Facultad de Ingeniería · UAEMéx (Equipo 404)
echo ========================================================================
echo.

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    py -3 --version >nul 2>&1 && set "PYTHON_CMD=py -3"
)

echo Abriendo navegador en http://127.0.0.1:8000/...
start http://127.0.0.1:8000/

echo.
echo Presiona Ctrl+C en esta ventana para detener el servidor.
echo ========================================================================
echo.

%PYTHON_CMD% main.py --serve
pause
