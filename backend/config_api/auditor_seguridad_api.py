#!/usr/bin/env python3
"""
Auditor de Seguridad de API Keys y Secretos
Proyecto: PotroBot UAEMéx (Ingeniería en Computación)
Verifica que las credenciales no estén en riesgo antes de subir a Git/Producción.
"""

import os
import re
import sys
from pathlib import Path

# Configure utf-8 stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_repo_root() -> Path:
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / ".git").exists() or (curr / ".gitignore").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = find_repo_root()

def print_header():
    print("=" * 65)
    print("     AUDITORIA DE SEGURIDAD DE CREDENCIALES Y GIT")
    print("     Nexus FI - Facultad de Ingenieria (UAEMex)")
    print("=" * 65)

def check_gitignore():
    gitignore_path = BASE_DIR / ".gitignore"
    if not gitignore_path.exists():
        return False, "Falta el archivo .gitignore en el proyecto."
    
    with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    has_env = bool(re.search(r'^\s*\.env\b', content, re.MULTILINE))
    if not has_env:
        return False, "El archivo .gitignore NO contiene la regla '.env'. Peligro de filtracion."
    return True, ".gitignore contiene '.env' correctamente configurado."

def scan_for_hardcoded_keys():
    """Scans code files for potential hardcoded API Keys."""
    suspicious_patterns = [
        re.compile(r'AIza[0-9A-Za-z\-_]{35}'),
        re.compile(r'AQ\.[0-9A-Za-z\-_]{30,55}')
    ]

    files_to_scan = []
    for ext in ["*.py", "*.js", "*.html", "*.bat", "*.sh"]:
        files_to_scan.extend(BASE_DIR.glob(f"**/{ext}"))

    leaks_found = []
    for filepath in files_to_scan:
        if ".env" in filepath.name or "venv" in str(filepath) or "__pycache__" in str(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if "AIzaSy..." in line or "AIza[0-9A-Za-z" in line or "AQ\\." in line:
                        continue
                    for pat in suspicious_patterns:
                        match = pat.search(line)
                        if match and "masked" not in line.lower() and "placeholder" not in line.lower():
                            leaks_found.append((filepath.relative_to(BASE_DIR), line_num, match.group(0)[:8] + "..."))
        except Exception:
            pass

    return leaks_found

def check_env_example():
    example_path = BASE_DIR / ".env.example"
    plantilla_path = BASE_DIR / "Confg API" / ".env.plantilla"
    return example_path.exists() or plantilla_path.exists()

def main():
    print_header()
    issues = 0

    # Test 1: Gitignore check
    print("\n[1/3] Verificando proteccion en .gitignore...")
    gi_ok, gi_msg = check_gitignore()
    if gi_ok:
        print(f"  [OK] SEGURO: {gi_msg}")
    else:
        print(f"  [ALERTA CRITICA]: {gi_msg}")
        issues += 1

    # Test 2: Hardcoded secrets scan
    print("\n[2/3] Escaneando codigo fuente en busca de claves quemadas...")
    leaks = scan_for_hardcoded_keys()
    if not leaks:
        print("  [OK] SEGURO: No se detectaron API Keys expuestas en el codigo fuente.")
    else:
        print("  [ALERTA DE SEGURIDAD]: Se encontraron posibles claves escritas en codigo:")
        for file_rel, line, sample in leaks:
            print(f"      - {file_rel} (linea {line}): Token sospechoso ({sample})")
        issues += 1

    # Test 3: Template check
    print("\n[3/3] Verificando plantilla publica sin secretos...")
    if check_env_example():
        print("  [OK] SEGURO: Existe plantilla (.env.example / .env.plantilla) para colaboradores.")
    else:
        print("  [AVISO]: Se recomienda crear un .env.example para documentar variables.")

    # Result summary
    print("\n" + "=" * 65)
    if issues == 0:
        print("  RESULTADO: [OK] EL PROYECTO ES 100% APTO PARA SUBIR A GITHUB")
        print("  Tus credenciales estan protegidas y fuera del control de versiones.")
    else:
        print(f"  RESULTADO: [ALERTA] SE DETECTARON {issues} PROBLEMA(S) DE SEGURIDAD")
        print("  Corrige las alertas antes de ejecutar 'git commit' o 'git push'.")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
