"""
network.py - Módulo de funciones de red

Este módulo contiene las funciones necesarias para:
- Crear un socket TCP
- Conectar al servidor
- Cerrar la conexión de forma segura

Utiliza únicamente la librería estándar 'socket' de Python.
"""

import socket


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
