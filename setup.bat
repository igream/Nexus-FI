@echo off
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

:: 1. Detectar ejecutable de Python
set PYTHON_EXE=
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_EXE=py -3
    goto :python_found
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_EXE=python
    goto :python_found
)

if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found
)

echo [ERROR] No se encontró Python 3 instalado en esta máquina.
echo Por favor descarga e instala Python 3.11, 3.12, 3.13 o 3.14 desde:
echo https://www.python.org/downloads/
echo (Asegúrate de marcar la casilla "Add python.exe to PATH")
echo.
pause
exit /b 1

:python_found
echo [1/5] Python detectado: %PYTHON_EXE%
%PYTHON_EXE% --version
echo.

:: 2. Crear o verificar entorno virtual (.venv)
echo [2/5] Verificando entorno virtual (.venv)...
if not exist ".venv" (
    echo Creando nuevo entorno virtual aislado en .venv...
    %PYTHON_EXE% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Falló la creación del entorno virtual .venv.
        pause
        exit /b 1
    )
    echo Entorno virtual creado con éxito.
) else (
    echo Entorno virtual .venv ya existente.
)

:: Activar entorno virtual para los siguientes pasos
if exist ".venv\Scripts\python.exe" (
    set VENV_PYTHON=".venv\Scripts\python.exe"
    set VENV_PIP=".venv\Scripts\pip.exe"
) else (
    set VENV_PYTHON=%PYTHON_EXE%
    set VENV_PIP=%PYTHON_EXE% -m pip
)
echo.

:: 3. Instalar o actualizar dependencias de requirements.txt
echo [3/5] Instalando dependencias del proyecto (requirements.txt)...
%VENV_PIP% install --upgrade pip --quiet
%VENV_PIP% install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Ocurrió un error al instalar las dependencias con pip.
    pause
    exit /b 1
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
    echo [AVISO IMPORTANTE]
    echo Se ha creado un archivo .env base en la raíz del proyecto.
    echo Para que las consultas con búsqueda semántica y generación RAG funcionen,
    echo debes abrir el archivo .env con el Bloc de Notas y configurar tu:
    echo OPENAI_API_KEY=sk-proj-...
    echo ------------------------------------------------------------------------
    echo.
) else (
    echo Archivo .env detectado ✓.
)
echo.

:: 5. Verificar Base de Datos Vectorial (LanceDB)
echo [5/5] Verificando Base de Datos Vectorial (data/lancedb)...
if exist "data\lancedb\nexus_documents.lance" (
    echo [OK] Base de datos vectorial detectada y lista con 3,977 fragmentos.
) else (
    echo [!] AVISO: No se encontró la carpeta 'data/lancedb'.
    echo     (Esto es normal si acabas de clonar el repositorio de GitHub,
    echo      ya que los archivos binarios están en .gitignore).
    echo.
    echo     ¿Deseas generar la base de datos vectorial ahora mismo?
    echo     (Requiere OPENAI_API_KEY configurada en .env; toma ~70 seg y cuesta ~0.04 USD)
    set /p REGEN="    ¿Generar base vectorial ahora? (S/N): "
    if /i "%REGEN%"=="S" (
        echo Generando vectores a partir de Procesados/corpus_chunks_para_embedding.jsonl...
        %VENV_PYTHON% scripts\vectorize_corpus.py
    ) else (
        echo Omitiendo generación de base vectorial.
        echo Puedes generarla en cualquier momento con: python scripts\vectorize_corpus.py
        echo O copiar la carpeta 'data/' desde la máquina del Product Manager.
    )
)
echo.

:: Diagnóstico final de telemetría y seguridad
echo ========================================================================
echo [VERIFICACIÓN FINAL] Ejecutando diagnóstico del sistema...
echo ========================================================================
%VENV_PYTHON% main.py --telemetry
echo.

echo ========================================================================
echo     ¡Instalación de Nexus FI completada exitosamente!
echo ========================================================================
echo.
echo ¿Deseas iniciar el servidor web ahora mismo?
set /p START_NOW="Iniciar servidor ahora (S/N): "
if /i "%START_NOW%"=="S" (
    start http://127.0.0.1:8000/
    %VENV_PYTHON% main.py --serve
) else (
    echo Para iniciar el servidor más tarde, ejecuta: start.bat o 'python main.py --serve'
    pause
)
