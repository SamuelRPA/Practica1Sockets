"""
network.py - Módulo de funciones de red

Este módulo contiene las funciones necesarias para:
- Crear un socket TCP
- Conectar al servidor
- Cerrar la conexión de forma segura
- Obtener y enviar las particiones del disco

Utiliza únicamente librerías estándar de Python.
"""

import socket
import shutil
import os
import string


def crear_socket():
    """
    Crea y retorna un socket TCP (IPv4).

    Returns:
        socket.socket: Un objeto socket configurado para TCP/IPv4.
    """
    # AF_INET  = IPv4
    # SOCK_STREAM = TCP (conexión orientada a flujo de datos)
    cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("[INFO] Socket creado exitosamente.")
    return cliente_socket


def conectar(cliente_socket, ip, puerto):
    """
    Conecta el socket al servidor especificado.

    Args:
        cliente_socket (socket.socket): El socket del cliente.
        ip (str): Dirección IP del servidor.
        puerto (int): Puerto del servidor.

    Returns:
        bool: True si la conexión fue exitosa, False en caso contrario.
    """
    try:
        cliente_socket.connect((ip, puerto))
        print(f"[✓] Conectado al servidor {ip}:{puerto}")
        return True
    except ConnectionRefusedError:
        print(f"[✗] Error: El servidor {ip}:{puerto} rechazó la conexión.")
        print("    Asegúrate de que el servidor esté en ejecución.")
        return False
    except socket.timeout:
        print(f"[✗] Error: Tiempo de espera agotado al conectar a {ip}:{puerto}.")
        return False
    except OSError as e:
        print(f"[✗] Error de red al conectar: {e}")
        return False


def cerrar_conexion(cliente_socket):
    """
    Cierra la conexión del socket de forma segura.

    Args:
        cliente_socket (socket.socket): El socket a cerrar.
    """
    try:
        cliente_socket.close()
        print("[INFO] Conexión cerrada correctamente.")
    except OSError as e:
        print(f"[!] Error al cerrar la conexión: {e}")


def obtener_particiones():
    """
    Obtiene información de todas las particiones/unidades del disco.

    Recorre las letras A-Z buscando unidades disponibles en el sistema.
    Para cada unidad encontrada, obtiene:
    - Espacio total
    - Espacio usado
    - Espacio libre

    Returns:
        list: Lista de diccionarios con info de cada partición.
              Cada diccionario tiene: 'unidad', 'total_gb', 'usado_gb', 'libre_gb'
    """
    particiones = []

    # Recorrer todas las letras posibles de unidades (A-Z)
    for letra in string.ascii_uppercase:
        ruta = f"{letra}:\\"

        # Verificar si la unidad existe y es accesible
        if os.path.exists(ruta):
            try:
                # shutil.disk_usage() retorna (total, used, free) en bytes
                uso = shutil.disk_usage(ruta)
                particiones.append({
                    "unidad": f"{letra}:",
                    "total_gb": round(uso.total / (1024 ** 3), 2),
                    "usado_gb": round(uso.used / (1024 ** 3), 2),
                    "libre_gb": round(uso.free / (1024 ** 3), 2),
                })
            except (PermissionError, OSError):
                # Unidad existe pero no se puede acceder (ej: CD-ROM vacío)
                particiones.append({
                    "unidad": f"{letra}:",
                    "total_gb": 0,
                    "usado_gb": 0,
                    "libre_gb": 0,
                })

    return particiones


def enviar_particiones(cliente_socket):
    """
    Obtiene las particiones del disco y las envía al servidor.

    Se llama automáticamente al conectarse al servidor.
    El mensaje se envía con un formato claro para que el servidor
    pueda interpretarlo.

    Args:
        cliente_socket (socket.socket): El socket conectado al servidor.

    Returns:
        bool: True si se envió correctamente, False si falló.
    """
    try:
        particiones = obtener_particiones()

        # Construir mensaje con la información de las particiones
        lineas = ["[INFO-DISCO] Particiones del cliente:"]
        lineas.append("-" * 45)

        for p in particiones:
            lineas.append(
                f"  {p['unidad']}  "
                f"Total: {p['total_gb']} GB | "
                f"Usado: {p['usado_gb']} GB | "
                f"Libre: {p['libre_gb']} GB"
            )

        lineas.append("-" * 45)
        mensaje = "\n".join(lineas)

        # Mostrar en la consola del cliente también
        print(f"\n{mensaje}\n")
        print("[INFO] Enviando información de particiones al servidor...")

        # Enviar al servidor
        cliente_socket.sendall(mensaje.encode("utf-8"))
        print("[✓] Particiones enviadas al servidor.\n")
        return True

    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[!] Error al enviar particiones: {e}")
        return False

