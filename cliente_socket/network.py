"""
network.py - Módulo de funciones de red

Este módulo contiene las funciones necesarias para:
- Crear un socket TCP
- Conectar al servidor
- Cerrar la conexión de forma segura
- Obtener info del sistema (disco, RAM) y enviarla en formato JSON
- Guardar/cargar log pendiente cuando el servidor se desconecta

Utiliza únicamente librerías estándar de Python.
"""

import socket
import shutil
import os
import string
import json
import time
import ctypes
import subprocess

# Archivo donde se guardan los datos pendientes si el servidor se desconecta
ARCHIVO_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_log.json")


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


# ═══════════════════════════════════════════════════════
#  FUNCIONES DE INFORMACIÓN DEL SISTEMA
# ═══════════════════════════════════════════════════════


def obtener_tipo_disco(letra_unidad):
    """
    Intenta detectar si una unidad es SSD o HDD usando PowerShell.

    Args:
        letra_unidad (str): Letra de la unidad sin ':' (ej: 'C')

    Returns:
        str: 'SSD', 'HDD' o 'Desconocido'
    """
    try:
        # Comando PowerShell para obtener el tipo de medio del disco físico
        cmd = (
            f"(Get-PhysicalDisk | Where-Object {{$_.DeviceID -eq "
            f"(Get-Partition -DriveLetter '{letra_unidad}' | "
            f"Get-Disk).Number}}).MediaType"
        )
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=10
        )
        tipo = resultado.stdout.strip()
        if "SSD" in tipo or "Solid" in tipo:
            return "SSD"
        elif "HDD" in tipo or "Hard" in tipo:
            return "HDD"
        return "Desconocido"
    except Exception:
        return "Desconocido"


def obtener_particiones():
    """
    Obtiene información de todas las particiones/unidades del disco.

    Returns:
        list: Lista de diccionarios con info de cada partición.
    """
    particiones = []

    for letra in string.ascii_uppercase:
        ruta = f"{letra}:\\"

        if os.path.exists(ruta):
            try:
                uso = shutil.disk_usage(ruta)
                tipo = obtener_tipo_disco(letra)
                particiones.append({
                    "nombre": f"{letra}:",
                    "tipo": tipo,
                    "total_gb": round(uso.total / (1024 ** 3), 2),
                    "used_gb": round(uso.used / (1024 ** 3), 2),
                    "free_gb": round(uso.free / (1024 ** 3), 2),
                    "iops": 0,  # No medible fácilmente con librería estándar
                })
            except (PermissionError, OSError):
                particiones.append({
                    "nombre": f"{letra}:",
                    "tipo": "Desconocido",
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "iops": 0,
                })

    return particiones


def obtener_info_ram():
    """
    Obtiene información de la memoria RAM y uptime del sistema.

    Usa ctypes para llamar a las APIs de Windows:
    - GlobalMemoryStatusEx: para obtener total/disponible de RAM
    - GetTickCount64: para obtener el tiempo de actividad del sistema

    Returns:
        dict: Diccionario con total_gb, used_gb, free_gb, uptime_seconds
    """
    try:
        # Estructura de Windows para información de memoria
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

        total_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
        free_gb = round(stat.ullAvailPhys / (1024 ** 3), 2)
        used_gb = round(total_gb - free_gb, 2)

        # Uptime del sistema en segundos (GetTickCount64 retorna milisegundos)
        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
        uptime_seconds = uptime_ms // 1000

        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "uptime_seconds": uptime_seconds,
        }

    except Exception:
        return {
            "total_gb": 0,
            "used_gb": 0,
            "free_gb": 0,
            "uptime_seconds": 0,
        }


def enviar_info_sistema(cliente_socket, nodo, display_name):
    """
    Construye el payload JSON con info del sistema y lo envía al servidor.

    Formato exacto esperado por el Stored Procedure y el Monitor:
    {"nodo":"...","display_name":"...","timestamp":...,"disco":{...},"ram":{...}}

    IMPORTANTE:
    - Se envía UN solo JSON compacto (sin indent)
    - Se usa el disco principal (C: o el primero disponible)
    - Se termina con \\n para que el servidor sepa dónde termina el mensaje

    Args:
        cliente_socket (socket.socket): Socket conectado al servidor.
        nodo (str): Identificador del nodo (ej: "cochabamba").
        display_name (str): Nombre visible del nodo (ej: "Cochabamba Central").

    Returns:
        bool: True si se envió correctamente, False si falló.
    """
    try:
        particiones = obtener_particiones()
        info_ram = obtener_info_ram()

        if not particiones:
            print("[!] No se detectaron particiones de disco.")
            return False

        # Usar el disco principal (C: si existe, o el primero disponible)
        disco_principal = particiones[0]
        for p in particiones:
            if p["nombre"] == "C:":
                disco_principal = p
                break

        print(f"\n[INFO] Disco principal: {disco_principal['nombre']} "
              f"({disco_principal['tipo']})")
        print(f"[INFO] RAM: {info_ram['total_gb']} GB total, "
              f"{info_ram['used_gb']} GB usado, "
              f"{info_ram['free_gb']} GB libre")
        print(f"[INFO] Uptime: {info_ram['uptime_seconds']} segundos\n")

        # Construir payload JSON exacto para el servidor
        payload = {
            "nodo": nodo,
            "display_name": display_name,
            "timestamp": time.time(),
            "disco": {
                "nombre": disco_principal["nombre"],
                "tipo": disco_principal["tipo"],
                "total_gb": disco_principal["total_gb"],
                "used_gb": disco_principal["used_gb"],
                "free_gb": disco_principal["free_gb"],
                "iops": disco_principal["iops"],
            },
            "ram": {
                "total_gb": info_ram["total_gb"],
                "used_gb": info_ram["used_gb"],
                "free_gb": info_ram["free_gb"],
                "uptime_seconds": info_ram["uptime_seconds"],
            },
        }

        # JSON compacto (sin indent) + salto de línea como terminador
        mensaje_json = json.dumps(payload) + "\n"

        # Mostrar en consola para debug
        print(f"[Enviando payload]:")
        print(json.dumps(payload, indent=2))

        # Enviar al servidor
        cliente_socket.sendall(mensaje_json.encode("utf-8"))
        print(f"\n[✓] Info del sistema enviada al servidor.\n")
        return True

    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[!] Error al enviar info del sistema: {e}")
        return False


def envio_periodico(cliente_socket, evento_activo, nodo, display_name, intervalo=15):
    """
    Envía la info del sistema al servidor periódicamente.

    Esta función está diseñada para ejecutarse en un thread independiente.
    Cada 'intervalo' segundos, recopila la info actual del sistema
    (disco, RAM, uptime) y la envía al servidor como JSON.

    Args:
        cliente_socket (socket.socket): Socket conectado al servidor.
        evento_activo (threading.Event): Evento para controlar el ciclo.
        nodo (str): Identificador del nodo.
        display_name (str): Nombre visible del nodo.
        intervalo (int): Segundos entre cada envío (default: 15).
    """
    # Esperar el primer intervalo antes de enviar
    # (la info inicial ya se envió al conectar)
    while evento_activo.is_set():
        # wait() retorna False si expira el timeout, True si el evento se limpia
        # Esto permite cancelar la espera inmediatamente al desconectar
        if not evento_activo.wait(timeout=intervalo):
            break

        if not evento_activo.is_set():
            break

        try:
            particiones = obtener_particiones()
            info_ram = obtener_info_ram()

            if not particiones:
                continue

            disco_principal = particiones[0]
            for p in particiones:
                if p["nombre"] == "C:":
                    disco_principal = p
                    break

            payload = {
                "nodo": nodo,
                "display_name": display_name,
                "timestamp": time.time(),
                "disco": {
                    "nombre": disco_principal["nombre"],
                    "tipo": disco_principal["tipo"],
                    "total_gb": disco_principal["total_gb"],
                    "used_gb": disco_principal["used_gb"],
                    "free_gb": disco_principal["free_gb"],
                    "iops": disco_principal["iops"],
                },
                "ram": {
                    "total_gb": info_ram["total_gb"],
                    "used_gb": info_ram["used_gb"],
                    "free_gb": info_ram["free_gb"],
                    "uptime_seconds": info_ram["uptime_seconds"],
                },
            }

            mensaje_json = json.dumps(payload) + "\n"
            cliente_socket.sendall(mensaje_json.encode("utf-8"))
            print(f"[AUTO] Métrica enviada al servidor ({intervalo}s)")

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            print("\n[!] Conexión perdida durante envío periódico.")
            evento_activo.clear()
            break
        except OSError:
            if evento_activo.is_set():
                print("\n[!] Error de red en envío periódico.")
            evento_activo.clear()
            break


# ═══════════════════════════════════════════════════════
#  FUNCIONES DE LOG PENDIENTE (desconexión del servidor)
# ═══════════════════════════════════════════════════════


def guardar_log_pendiente(nodo, display_name):
    """
    Guarda la info actual del sistema en un archivo de log local.

    Se llama cuando el servidor se desconecta, para que al
    volver a conectarse se pueda reenviar la información.

    El archivo se guarda como 'pending_log.json' en la carpeta del proyecto.

    Args:
        nodo (str): Identificador del nodo.
        display_name (str): Nombre visible del nodo.
    """
    try:
        particiones = obtener_particiones()
        info_ram = obtener_info_ram()

        if not particiones:
            print("[!] No se pudieron obtener particiones para el log.")
            return

        # Usar disco principal (C: o el primero)
        disco_principal = particiones[0]
        for p in particiones:
            if p["nombre"] == "C:":
                disco_principal = p
                break

        payload = {
            "nodo": nodo,
            "display_name": display_name,
            "timestamp": time.time(),
            "disco": {
                "nombre": disco_principal["nombre"],
                "tipo": disco_principal["tipo"],
                "total_gb": disco_principal["total_gb"],
                "used_gb": disco_principal["used_gb"],
                "free_gb": disco_principal["free_gb"],
                "iops": disco_principal["iops"],
            },
            "ram": {
                "total_gb": info_ram["total_gb"],
                "used_gb": info_ram["used_gb"],
                "free_gb": info_ram["free_gb"],
                "uptime_seconds": info_ram["uptime_seconds"],
            },
        }

        # Guardar en archivo JSON
        with open(ARCHIVO_LOG, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(f"\n{'=' * 50}")
        print(f"  [LOG] Datos guardados en: {ARCHIVO_LOG}")
        print(f"  [LOG] Se reenviarán al reconectarse.")
        print(f"{'=' * 50}\n")

    except Exception as e:
        print(f"[!] Error al guardar log pendiente: {e}")


def cargar_log_pendiente():
    """
    Carga el payload pendiente desde el archivo de log.

    Returns:
        dict o None: El payload guardado, o None si no hay log pendiente.
    """
    if not os.path.exists(ARCHIVO_LOG):
        return None

    try:
        with open(ARCHIVO_LOG, "r", encoding="utf-8") as f:
            payload = json.load(f)
        print(f"\n[LOG] Se encontró un log pendiente de la sesión anterior.")
        print(f"[LOG] Nodo: {payload.get('nodo', '?')} | "
              f"Disco: {payload.get('disco', {}).get('nombre', '?')}")
        return payload
    except (json.JSONDecodeError, OSError) as e:
        print(f"[!] Error al leer log pendiente: {e}")
        return None


def eliminar_log_pendiente():
    """
    Elimina el archivo de log pendiente después de reenviarlo.
    """
    try:
        if os.path.exists(ARCHIVO_LOG):
            os.remove(ARCHIVO_LOG)
            print("[LOG] Log pendiente eliminado.")
    except OSError as e:
        print(f"[!] Error al eliminar log pendiente: {e}")


def reenviar_log_pendiente(cliente_socket):
    """
    Verifica si hay un log pendiente y lo reenvía al servidor.

    Se llama automáticamente al conectarse. Si hay datos pendientes
    de una sesión anterior (cuando el servidor se desconectó), los
    reenvía con un timestamp actualizado y luego elimina el archivo.

    Args:
        cliente_socket (socket.socket): Socket conectado al servidor.

    Returns:
        bool: True si se reenvió (o no había nada pendiente), False si falló.
    """
    payload = cargar_log_pendiente()

    if payload is None:
        # No hay log pendiente, todo bien
        return True

    try:
        # Actualizar timestamp al momento actual
        payload["timestamp"] = time.time()

        mensaje_json = json.dumps(payload) + "\n"

        print(f"[LOG] Reenviando datos pendientes al servidor...")
        print(json.dumps(payload, indent=2))

        cliente_socket.sendall(mensaje_json.encode("utf-8"))
        print(f"\n[✓] Datos pendientes reenviados exitosamente.")

        # Eliminar el log ya que se envió correctamente
        eliminar_log_pendiente()
        return True

    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[!] Error al reenviar log pendiente: {e}")
        return False
