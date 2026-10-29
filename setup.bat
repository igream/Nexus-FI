@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
title Nexus FI — Instalador y Configurador Automatizado
color 0A

echo ========================================================================
echo        _   _ _____ _   _ _   _ ____    _____ ___
echo       ^| \ ^| ^| ____^| \ ^| ^| ^| ^| / ___^|  ^|  ___^|_ _^|
echo       ^|  \^| ^|  _^| ^|  \^| ^| ^| ^| \___ \  ^| ^|_   ^| ^|
echo       ^| ^|\  ^| ^|___^| ^|\  ^| ^|_^| ^|___) ^| ^|  _^|  ^| ^|
echo       ^|_^| \_^|_____^|_^| \_^|\___/^|____/  ^|_^|   ^|___^|
echo.
echo     Instalador Automatizado y Configuración de Entorno (Setup)
echo            Facultad de Ingeniería · UAEMéx (Equipo 404)
echo ========================================================================
echo.
echo  Prepara un proyecto recién clonado: Python, entorno virtual y dependencias.
echo  El archivo .env y la base vectorial data\lancedb se copian a mano (al final
echo  se indica qué falta).
echo.

:: ---------------------------------------------------------------------------
:: 1. Detección robusta de Python >= 3.10 (descarta alias de WindowsApps)
:: ---------------------------------------------------------------------------
set "PYTHON_EXE="

py -3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :python_found
)

python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    goto :python_found
)

for %%P in (
    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    "%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python310\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=%%~P"
            goto :python_found
        )
    )
)

echo [ERROR] No se encontró una instalación funcional de Python ^>= 3.10 en este equipo.
echo Si acabas de instalar Python o aparece el alias de Microsoft Store:
echo  1. Descarga Python desde: https://www.python.org/downloads/
echo  2. IMPORTANTE: Marca la casilla "Add python.exe to PATH" en el instalador.
echo  3. Vuelve a ejecutar este archivo setup.bat.
echo.
pause
exit /b 1

:python_found
echo [1/4] Python verificado correctamente:
if "%PYTHON_EXE%"=="py -3" (
    py -3 --version
) else (
    "%PYTHON_EXE%" --version
)
echo.

:: ---------------------------------------------------------------------------
:: 2. Crear o verificar entorno virtual (.venv)
:: ---------------------------------------------------------------------------
echo [2/4] Verificando entorno virtual (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo Creando nuevo entorno virtual aislado en .venv...
    if "%PYTHON_EXE%"=="py -3" (
        py -3 -m venv .venv
    ) else (
        "%PYTHON_EXE%" -m venv .venv
    )
    if !errorlevel! neq 0 (
        echo [ERROR] Falló la creación del entorno virtual .venv.
        echo Asegúrate de tener permisos de escritura en esta carpeta.
        pause
        exit /b 1
    )
    echo Entorno virtual creado con éxito.
) else (
    echo Entorno virtual .venv ya existente.
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
echo.

:: ---------------------------------------------------------------------------
:: 3. Instalar o actualizar dependencias de requirements.txt
:: ---------------------------------------------------------------------------
echo [3/4] Instalando dependencias del proyecto (requirements.txt)...
echo       Puede tardar varios minutos la primera vez.
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel --quiet
"%VENV_PYTHON%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ocurrió un error al instalar las dependencias con pip.
    echo Revisa el mensaje de error de arriba. Causas frecuentes:
    echo  - Falta de conexión a Internet.
    echo  - Un paquete sin versión para tu Python:
    "%VENV_PYTHON%" --version
    echo    En ese caso instala Python 3.12 y borra la carpeta .venv antes de reintentar.
    echo  - Faltan las librerías de Microsoft Visual C++ 2015-2022:
    echo    https://aka.ms/vs/17/release/vc_redist.x64.exe
    pause
    exit /b 1
)

"%VENV_PYTHON%" -c "import lancedb, pyarrow, pandas, fastapi, uvicorn, openai" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Las dependencias se instalaron pero no cargan correctamente.
    echo Si observas errores de DLL, instala Microsoft Visual C++ 2015-2022:
    echo https://aka.ms/vs/17/release/vc_redist.x64.exe
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas y verificadas.
echo.

:: ---------------------------------------------------------------------------
:: 4. Verificar lo que no viene en el repositorio (.env y base vectorial)
:: ---------------------------------------------------------------------------
echo [4/4] Verificando archivos que se copian a mano...
set "ENV_OK=0"
set "DB_OK=0"
if exist ".env" set "ENV_OK=1"
if exist "data\lancedb\nexus_documents.lance" set "DB_OK=1"

if "%ENV_OK%%DB_OK%"=="11" (
    echo [OK] .env y data\lancedb presentes. Ejecutando diagnóstico del sistema...
    echo.
    "%VENV_PYTHON%" main.py --telemetry
)

:: ---------------------------------------------------------------------------
:: Resumen final
:: ---------------------------------------------------------------------------
echo.
echo ========================================================================
echo                       RESUMEN DE LA INSTALACIÓN
echo ========================================================================
echo   [OK]    Python, entorno virtual .venv y dependencias
if "%ENV_OK%"=="1" (
    echo   [OK]    Archivo .env
) else (
    echo   [FALTA] Archivo .env  ^(claves de OpenAI y subredes de la FI^)
)
if "%DB_OK%"=="1" (
    echo   [OK]    Base vectorial data\lancedb
) else (
    echo   [FALTA] Base vectorial data\lancedb  ^(3,977 vectores, ~59 MB^)
)
echo ========================================================================

if "%ENV_OK%%DB_OK%"=="11" goto :ready

echo.
echo  PASOS PENDIENTES (nunca se suben a GitHub; cópialos de un equipo donde ya
echo  funcione Nexus FI, por USB o unidad compartida):
echo.
if "%ENV_OK%"=="0" (
    echo   - Copia el archivo .env a:
    echo       %~dp0.env
    echo     ^(Si tienes tus propias claves, puedes partir de .env.example^)
    echo.
)
if "%DB_OK%"=="0" (
    echo   - Copia la carpeta completa lancedb a:
    echo       %~dp0data\lancedb
    echo     ^(Regenerarla con scripts\vectorize_corpus.py cuesta tiempo y créditos^)
    echo.
)
echo  Después ejecuta de nuevo setup.bat para verificar, o directamente start.bat.
echo.
pause
exit /b 0

:ready
echo.
echo  ¡Instalación de Nexus FI completada! Para iniciar el servidor en el futuro,
echo  haz doble clic en start.bat (te dejará elegir el modo desarrollo o FI).
echo.
set /p START_NOW="¿Deseas iniciar Nexus FI ahora mismo? (S/N): "
if /i "!START_NOW!"=="S" (
    call "%~dp0start.bat"
) else (
    pause
)
exit /b 0
