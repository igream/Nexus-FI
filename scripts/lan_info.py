"""
Imprime la IP de este equipo en la red local y si pertenece a las subredes de la FI.
Lo usa start.bat para abrir el navegador con la IP correcta y avisar antes de iniciar
el modo FI. Salida (una línea): <ip>|<1 si está en la red FI, 0 si no>
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no envía tráfico; solo elige la interfaz
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = lan_ip()
    try:
        from core.security.ip_filter import is_ip_in_perimeter
        in_fi = is_ip_in_perimeter(ip)
    except Exception:
        in_fi = False
    print(f"{ip}|{1 if in_fi else 0}")
