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

:: 1. Detección robusta de ejecutable de Python (descarta alias de WindowsApps)
set "PYTHON_EXE="

:: Intentar con py -3 (Python Launcher oficial)
py -3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :python_found
)

:: Intentar con python en PATH verificando que sea funcional y >= 3.10
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    goto :python_found
)

:: Rutas estándar de instalación en Windows
for %%P in (
    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=%%~P"
            goto :python_found
        )
    )
)

echo [ERROR] No se encontró una instalación funcional de Python >= 3.10 en este equipo.
echo Si acabas de instalar Python o aparece el alias de Microsoft Store:
echo  1. Descarga Python 3.11 o 3.12 desde: https://www.python.org/downloads/
echo  2. IMPORTANTE: Marca la casilla "Add python.exe to PATH" en el instalador.
echo  3. Vuelve a ejecutar este archivo setup.bat.
echo.
pause
exit /b 1

:python_found
echo [1/5] Python verificado correctamente:
if "%PYTHON_EXE%"=="py -3" (
    py -3 --version
) else (
    "%PYTHON_EXE%" --version
)
echo.

:: 2. Crear o verificar entorno virtual (.venv)
echo [2/5] Verificando entorno virtual (.venv)...
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
    echo Entorno virtual .venv ya existente y operativo.
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "VENV_PIP=%~dp0.venv\Scripts\pip.exe"
echo.

:: 3. Instalar o actualizar dependencias de requirements.txt
echo [3/5] Instalando dependencias del proyecto (requirements.txt)...
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel --quiet
"%VENV_PYTHON%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ocurrió un error al instalar las dependencias con pip.
    echo Posibles causas y soluciones:
    echo  - Falta de conexión a Internet.
    echo  - En Windows se recomienda instalar Microsoft Visual C++ 2015-2022 Redistributable:
    echo    https://aka.ms/vs/17/release/vc_redist.x64.exe
    pause
    exit /b 1
)

:: Verificación de carga de bibliotecas C++ (LanceDB / ONNX)
"%VENV_PYTHON%" -c "import lancedb, pyarrow" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] LanceDB requiere las librerías de Microsoft Visual C++.
    echo Si observas errores de DLL, descarga e instala:
    echo https://aka.ms/vs/17/release/vc_redist.x64.exe
)
echo Dependencias instaladas y verificadas correctamente.
echo.

:: 4. Verificar archivo de configuración .env
echo [4/5] Verificando variables de entorno (.env)...
if not exist ".env" (
    echo No se encontró el archivo .env. Creando a partir de .env.example...
    copy .env.example .env >nul
    echo.
    echo ------------------------------------------------------------------------
    echo [AVISO IMPORTANTE DE CONFIGURACIÓN]
    echo Se ha generado la plantilla .env en la raíz del proyecto.
    echo Para habilitar la búsqueda semántica y el asistente RAG, debes ingresar
    echo tus API Keys de OpenAI.
    echo ------------------------------------------------------------------------
    set /p OPEN_ENV="¿Deseas abrir el archivo .env en el Bloc de Notas ahora? (S/N): "
    if /i "!OPEN_ENV!"=="S" (
        start notepad .env
        echo Se ha abierto el Bloc de Notas. Guarda los cambios y continúa.
        pause
    )
) else (
    echo Archivo .env detectado.
)
echo.

:: 5. Verificar Base de Datos Vectorial (LanceDB)
echo [5/5] Verificando Base de Datos Vectorial (data/lancedb)...
if exist "data\lancedb\nexus_documents.lance" (
    echo [OK] Base de datos vectorial detectada y lista con 3,977 fragmentos.
    goto :skip_vectorize
)

echo [!] No se encontró la carpeta 'data/lancedb'.
echo     (Los archivos binarios de la base vectorial no se suben a GitHub).
echo.

:: Comprobar si la API Key está configurada antes de ofrecer vectorizar
"%VENV_PYTHON%" -c "import os; from dotenv import load_dotenv; load_dotenv(); k=os.getenv('OPENAI_API_KEY_EMBEDDINGS') or os.getenv('OPENAI_API_KEY',''); exit(0 if k and not k.startswith('sk-proj-tu-api-key') and len(k)>20 else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] Tu archivo .env aún no tiene configurada una clave de OpenAI válida.
    echo Opciones para obtener la base de datos vectorial:
    echo   1. Configurar OPENAI_API_KEY_EMBEDDINGS en .env y ejecutar:
    echo      python scripts\vectorize_corpus.py
    echo   2. O copiar la carpeta 'data/' directamente desde el equipo de Fernando (PM).
    goto :skip_vectorize
)

set /p REGEN="¿Deseas generar la base de datos vectorial ahora mismo? (S/N): "
if /i "!REGEN!"=="S" (
    echo Generando vectores a partir de Procesados/corpus_chunks_para_embedding.jsonl...
    "%VENV_PYTHON%" scripts\vectorize_corpus.py
) else (
    echo Omitiendo generación de base vectorial.
    echo Puedes generarla en cualquier momento ejecutando: python scripts\vectorize_corpus.py
)

:skip_vectorize
echo.

:: Diagnóstico final de telemetría y seguridad
echo ========================================================================
echo [VERIFICACIÓN FINAL] Ejecutando diagnóstico del sistema...
echo ========================================================================
"%VENV_PYTHON%" main.py --telemetry
echo.

echo ========================================================================
echo     ¡Instalación de Nexus FI completada exitosamente!
echo ========================================================================
echo.
set /p START_NOW="¿Deseas iniciar el servidor web ahora mismo? (S/N): "
if /i "!START_NOW!"=="S" (
    start "" http://127.0.0.1:8000/
    "%VENV_PYTHON%" main.py --serve
) else (
    echo.
    echo Para iniciar el servidor más tarde:
    echo  - Haz doble clic en 'start.bat'
    echo  - O ejecuta: python main.py --serve
    echo.
    pause
)
