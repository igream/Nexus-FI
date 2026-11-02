"""
Imprime la IP de este equipo en la red local.
Lo usa start.bat para abrir el navegador con la dirección correcta cuando el
servidor se inicia en la red. Salida (una línea): <ip>
"""
import socket


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no envía tráfico; solo elige la interfaz
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    print(lan_ip())
