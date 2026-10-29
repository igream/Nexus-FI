#!/usr/bin/env python3
"""
security_vault.py — Gestor de Bóveda y Seguridad de Secretos Locales
Facultad de Ingeniería UAEMéx — Nexus FI (Equipo 404)
Project Manager: Fernando Azuara Ibarra

Funcionalidades:
1. Migrar API Keys y Subredes de .env a Variables de Entorno de Usuario de Windows (HKCU).
2. Instalar Pre-Commit Hook en Git para bloquear commits accidentales con secretos.
3. Verificar el estado de seguridad de credenciales locales.
"""

import os
import sys
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
HOOK_PATH = BASE_DIR / ".git" / "hooks" / "pre-commit"

# Patrones de secretos conocidos
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
]

SENSITIVE_KEYS = [
    "OPENAI_API_KEY_EMBEDDINGS",
    "OPENAI_API_KEY_CHAT_4O_MINI",
    "OPENAI_API_KEY_GPT6_LUNA",
    "OPENAI_API_KEY_GPT5_6_LUNA",
    "OPENAI_API_KEY",
    "OPENAI_API_KEY_CHAT",
    "GEMINI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AUTHORIZED_SUBNETS",
]


def load_env_dict(path: Path) -> dict:
    """Lee un archivo .env y retorna un diccionario con sus claves y valores."""
    data = {}
    if not path.exists():
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def sync_to_windows_user_env():
    """
    Copia las claves sensibles desde .env hacia las Variables de Entorno
    de Usuario de Windows (HKCU\\Environment).
    De esta forma quedan protegidas en tu perfil del SO y no es necesario
    tener el archivo .env físico en la carpeta del proyecto.
    """
    if sys.platform != "win32":
        print("[!] La sincronización con variables de usuario está disponible para Windows.")
        return

    data = load_env_dict(ENV_PATH)
    if not data:
        print("[-] No se encontró archivo .env con credenciales para sincronizar.")
        return

    print("=================================================================")
    print(" SINCRONIZACIÓN DE SECRETOS CON VARIABLES DE USUARIO DE WINDOWS")
    print("=================================================================")

    migrated = 0
    import winreg
    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            for var_name in SENSITIVE_KEYS:
                if var_name in data and data[var_name]:
                    val = data[var_name]
                    winreg.SetValueEx(key, var_name, 0, winreg.REG_SZ, val)
                    masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
                    print(f" [OK] {var_name} guardada en Windows User Env: {masked}")
                    migrated += 1
    except Exception as e:
        print(f"[Error al acceder al registro de Windows]: {e}")
        return

    print("-----------------------------------------------------------------")
    print(f"[+] Total de variables aseguradas en tu perfil de Windows: {migrated}")
    print("[+] Ahora cualquier proceso o terminal en tu PC puede leerlas sin")
    print("    depender de un archivo .env en texto plano.")
    print("=================================================================")


def install_git_precommit_hook():
    """Instala un hook pre-commit que audita staged files antes de crear un commit."""
    if not (BASE_DIR / ".git").exists():
        print("[-] No se detectó repositorio Git.")
        return

    HOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    hook_script = f"""#!/bin/sh
# Hook de Ciberseguridad Nexus FI - Bloqueo automático de fugas de API Keys y .env
python "{Path(__file__).resolve()}" --check-staged
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[ALERTA DE SEGURIDAD] Commit cancelado. Se detectaron posibles secretos o archivos .env en staged."
    exit 1
fi
exit 0
"""
    with open(HOOK_PATH, "w", encoding="utf-8") as f:
        f.write(hook_script)

    # Otorgar permisos en sistemas tipo POSIX si aplica
    try:
        os.chmod(HOOK_PATH, 0o755)
    except Exception:
        pass

    print("[+] Pre-commit hook instalado exitosamente en .git/hooks/pre-commit")


def check_staged_files() -> int:
    """Verifica si algún archivo en el staging area de Git contiene API keys o es .env."""
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            encoding="utf-8",
            errors="ignore",
        )
        staged_files = [f.strip() for f in diff_output.splitlines() if f.strip()]

        for sf in staged_files:
            if sf == ".env" or sf.startswith(".env.") and not sf.endswith(".example"):
                print(f"[BLOQUEO] Intento de commitear archivo sensible: {sf}")
                return 1

        # Revisar contenido de los diffs
        patch_output = subprocess.check_output(
            ["git", "diff", "--cached"],
            encoding="utf-8",
            errors="ignore",
        )

        for line in patch_output.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                for pattern in SECRET_PATTERNS:
                    found = pattern.findall(line)
                    # Ignorar dummies conocidos
                    real_found = [
                        m for m in found
                        if not any(dummy in m for dummy in ["tu-key", "tu-clave", "aqui", "ejemplo", "example"])
                    ]
                    if real_found:
                        print(f"[BLOQUEO] Se detectó posible clave API en el código que vas a commitear:")
                        print(f"          Patrón detectado: {real_found[0][:8]}... (Línea: {line[:50]}...)")
                        return 1

        return 0
    except Exception as e:
        print(f"[Aviso] No se pudo completar el check staged: {e}")
        return 0


def status_report():
    """Genera un reporte del estado de seguridad local de credenciales."""
    print("=================================================================")
    print(" REPORTE DE SEGURIDAD LOCAL DE CREDENCIALES (NEXUS FI)")
    print("=================================================================")
    
    # 1. Verificar .env en disco
    if ENV_PATH.exists():
        print(f" • Archivo .env en disco:        PRESENTE ({ENV_PATH.stat().st_size} bytes)")
    else:
        print(" • Archivo .env en disco:        NO EXISTE (Excelente para compartir el repo)")

    # 2. Verificar Variables de Usuario de Windows
    print(" • Estado en Windows User Env:")
    for k in SENSITIVE_KEYS[:5]:
        val = os.environ.get(k)
        if val:
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            print(f"    - {k}: CONFIGURADA ({masked})")
        else:
            print(f"    - {k}: No detectada en sesión actual")

    # 3. Hook pre-commit
    hook_installed = HOOK_PATH.exists()
    print(f" • Pre-commit Hook activo:       {'SÍ (Protegido)' if hook_installed else 'NO (Instalar con --install-hook)'}")
    print("=================================================================")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--sync-windows":
            sync_to_windows_user_env()
        elif arg == "--install-hook":
            install_git_precommit_hook()
        elif arg == "--check-staged":
            sys.exit(check_staged_files())
        elif arg == "--status":
            status_report()
        else:
            print("Opciones disponibles:")
            print("  --sync-windows   Copia claves de .env a Variables de Usuario Windows")
            print("  --install-hook   Instala el blindaje pre-commit en Git")
            print("  --status         Muestra el diagnóstico de seguridad local")
    else:
        status_report()
