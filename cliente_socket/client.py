"""
client.py - Archivo principal del cliente TCP

Este es el punto de entrada del programa. Se encarga de:
- Solicitar al usuario la IP y puerto del servidor
- Solicitar un nombre de usuario (opcional)
- Crear el socket y conectar al servidor
- Iniciar los threads de envío y recepción
- Controlar el ciclo de vida de la aplicación

Ejecución:
    python client.py

Uso de Threading para Bidireccionalidad:
    ┌──────────────────────────────────────────────┐
    │              CLIENTE TCP                     │
    │                                              │
    │   Thread Principal                           │
    │       │                                      │
    │       ├── Thread 1 (Emisor/Sender)           │
    │       │   └── Lee input del usuario          │
    │       │       └── Envía al servidor          │
    │       │                                      │
    │       └── Thread 2 (Receptor/Receiver)       │
    │           └── Escucha al servidor            │
    │               └── Muestra en pantalla        │
    │                                              │
    │   Ambos threads se ejecutan simultáneamente  │
    │   gracias a threading, permitiendo enviar    │
    │   y recibir mensajes al mismo tiempo.        │
    └──────────────────────────────────────────────┘
"""

import threading
import sys
import time

# Importar módulos del proyecto
from network import (crear_socket, conectar, cerrar_conexion,
                     enviar_info_sistema, reenviar_log_pendiente,
                     guardar_log_pendiente, envio_periodico)
from receiver import recibir_mensajes
from sender import enviar_mensajes


def solicitar_datos_conexion():
    """
    Solicita al usuario la IP, puerto, nombre de usuario, nodo y display_name.

    Returns:
        tuple: (ip, puerto, nombre_usuario, nodo, display_name)
    """
    print("\n" + "=" * 50)
    print("   CLIENTE TCP - Comunicación Bidireccional")
    print("=" * 50 + "\n")

    # Solicitar dirección IP del servidor
    ip = input("Ingrese IP del servidor (Enter para 127.0.0.1): ").strip()
    if not ip:
        ip = "127.0.0.1"  # Localhost por defecto

    # Solicitar puerto del servidor
    puerto_str = input("Ingrese puerto (Enter para 5000): ").strip()
    if not puerto_str:
        puerto = 5000  # Puerto por defecto
    else:
        try:
            puerto = int(puerto_str)
            if not (1 <= puerto <= 65535):
                print("[!] Puerto fuera de rango. Usando 5000.")
                puerto = 5000
        except ValueError:
            print("[!] Puerto inválido. Usando 5000.")
            puerto = 5000

    # Solicitar nombre de usuario (funcionalidad extra)
    nombre = input("Ingrese su nombre de usuario (Enter para 'Cliente'): ").strip()
    if not nombre:
        nombre = "Cliente"

    # Solicitar identificador del nodo (para el payload JSON del servidor)
    nodo = input("Ingrese nombre del nodo (ej: cochabamba): ").strip()
    if not nodo:
        nodo = "nodo_default"

    # Solicitar nombre visible del nodo
    display_name = input("Ingrese display name del nodo (ej: Cochabamba Central): ").strip()
    if not display_name:
        display_name = nodo.capitalize()

    return ip, puerto, nombre, nodo, display_name


def iniciar_cliente():
    """
    Función principal que coordina todo el flujo del cliente:

    1. Solicita datos de conexión al usuario
    2. Crea el socket TCP
    3. Conecta al servidor
    4. Crea un evento compartido para coordinar los threads
    5. Inicia el thread receptor (escucha mensajes del servidor)
    6. Inicia el thread emisor (envía mensajes del usuario)
    7. Espera a que ambos threads terminen
    8. Cierra la conexión de forma segura
    """
    # ── Paso 1: Solicitar datos ──
    ip, puerto, nombre_usuario, nodo, display_name = solicitar_datos_conexion()

    # ── Paso 2: Crear el socket ──
    cliente_socket = crear_socket()

    # ── Paso 3: Conectar al servidor ──
    if not conectar(cliente_socket, ip, puerto):
        cerrar_conexion(cliente_socket)
        sys.exit(1)

    # ── Paso 3.5: Reenviar log pendiente (si existe de sesión anterior) ──
    reenviar_log_pendiente(cliente_socket)

    # ── Paso 3.6: Enviar info del sistema al servidor (JSON) ──
    # Se envía automáticamente: disco, RAM, timestamp, nodo
    enviar_info_sistema(cliente_socket, nodo, display_name)

    # ── Paso 4: Crear evento de coordinación ──
    # threading.Event() es un mecanismo de sincronización entre threads.
    # Cuando está "set" (activo), los threads siguen funcionando.
    # Cuando está "clear" (inactivo), los threads saben que deben terminar.
    evento_activo = threading.Event()
    evento_activo.set()  # Activar: el cliente está conectado y funcionando

    # ── Paso 5: Crear e iniciar el thread RECEPTOR ──
    # daemon=True permite que el thread se cierre automáticamente
    # cuando el programa principal termina
    hilo_receptor = threading.Thread(
        target=recibir_mensajes,
        args=(cliente_socket, evento_activo),
        name="HiloReceptor",
        daemon=True,
    )
    hilo_receptor.start()

    # ── Paso 6: Crear e iniciar el thread EMISOR ──
    hilo_emisor = threading.Thread(
        target=enviar_mensajes,
        args=(cliente_socket, evento_activo, nombre_usuario),
        name="HiloEmisor",
        daemon=True,
    )
    hilo_emisor.start()

    # ── Paso 7: Crear e iniciar el thread PERIÓDICO ──
    # Envía métricas del sistema cada 15 segundos
    hilo_periodico = threading.Thread(
        target=envio_periodico,
        args=(cliente_socket, evento_activo, nodo, display_name, 15),
        name="HiloPeriodico",
        daemon=True,
    )
    hilo_periodico.start()
    print("[INFO] Envío periódico activado (cada 15 segundos).")

    # ── Paso 7: Esperar a que los threads terminen ──
    # El thread emisor termina cuando el usuario escribe /salir
    # o cuando la conexión se pierde
    try:
        while evento_activo.is_set():
            # Revisar periódicamente si la conexión sigue activa
            time.sleep(0.5)
    except KeyboardInterrupt:
        # El usuario presionó Ctrl+C
        print("\n[INFO] Interrupción detectada (Ctrl+C). Cerrando...")
        evento_activo.clear()

    # ── Paso 8: Guardar log si el servidor se desconectó ──
    # Si la desconexión NO fue por /salir del usuario, guardar datos
    # para reenviar en la próxima conexión
    guardar_log_pendiente(nodo, display_name)

    # ── Paso 9: Cerrar conexión de forma segura ──
    time.sleep(0.5)
    cerrar_conexion(cliente_socket)

    print("\n[✓] Cliente finalizado. ¡Hasta pronto!")


# ── Punto de entrada ──
if __name__ == "__main__":
    iniciar_cliente()
