# 🖧 Cliente TCP con Comunicación Bidireccional

Proyecto de práctica universitaria que implementa un **cliente TCP** en Python
utilizando **sockets** y **threading** para lograr comunicación bidireccional
simultánea con un servidor.

---

## 📚 Conceptos Clave

### ¿Qué es un Socket?

Un **socket** es un punto final de comunicación entre dos programas que se
ejecutan en una red. Funciona como un "enchufe" virtual que permite enviar y
recibir datos entre un cliente y un servidor.

En Python, usamos la librería estándar `socket` para crear conexiones TCP/IP:

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Socket TCP/IPv4
```

- **`AF_INET`**: Indica que usamos IPv4
- **`SOCK_STREAM`**: Indica protocolo TCP (orientado a conexión, fiable)

### ¿Qué es la Comunicación Bidireccional?

La **comunicación bidireccional** permite que tanto el cliente como el servidor
puedan enviar y recibir mensajes **al mismo tiempo**, sin que una operación
bloquee a la otra.

```
┌──────────┐                    ┌──────────┐
│          │ ──── Enviar ─────> │          │
│ CLIENTE  │                    │ SERVIDOR │
│          │ <── Recibir ────── │          │
└──────────┘                    └──────────┘
```

Esto se logra usando **threads** (hilos de ejecución):

| Thread        | Función                     |
| ------------- | --------------------------- |
| **Emisor**    | Lee input → Envía al servidor |
| **Receptor**  | Escucha al servidor → Muestra en pantalla |

Ambos threads se ejecutan **simultáneamente**, lo que permite escribir mensajes
mientras se reciben otros del servidor.

---

## 📂 Estructura del Proyecto

```
cliente_socket/
│
├── client.py      # Archivo principal: conexión + threads
├── network.py     # Funciones de red: crear socket, conectar, cerrar
├── receiver.py    # Hilo receptor: escucha mensajes del servidor
├── sender.py      # Hilo emisor: lee y envía mensajes del usuario
└── README.md      # Este archivo
```

---

## 🚀 Cómo Ejecutar

### Prerrequisitos

- Python 3.11 o superior
- Un servidor TCP en ejecución (ver sección "Servidor de Prueba")

### Ejecutar el cliente

```bash
cd cliente_socket
python client.py
```

### Ejemplo de Ejecución

```
==================================================
   CLIENTE TCP - Comunicación Bidireccional
==================================================

Ingrese IP del servidor (Enter para 127.0.0.1): 127.0.0.1
Ingrese puerto (Enter para 5000): 5000
Ingrese su nombre de usuario (Enter para 'Cliente'): Juan

[INFO] Socket creado exitosamente.
[✓] Conectado al servidor 127.0.0.1:5000

==================================================
  ¡Conexión establecida!
  Escribe tus mensajes y presiona Enter para enviar.
  Escribe /salir para desconectarte.
==================================================

Hola servidor
[Servidor]: ¡Bienvenido Juan!

¿Cómo estás?
[Servidor]: Todo bien, gracias por conectarte.

/salir
[INFO] Desconectando del servidor...
[INFO] Conexión cerrada correctamente.

[✓] Cliente finalizado. ¡Hasta pronto!
```

---

## 🔧 Servidor de Prueba

Si no tienes un servidor, puedes usar este mini-servidor para probar:

Crea un archivo `servidor_prueba.py` en la misma carpeta:

```python
"""
servidor_prueba.py - Servidor TCP de prueba (eco)

Acepta conexiones de clientes y reenvía los mensajes
recibidos de vuelta al cliente (servidor eco).

Ejecución:
    python servidor_prueba.py
"""

import socket
import threading


def manejar_cliente(conn, addr):
    """Maneja la comunicación con un cliente conectado."""
    print(f"[+] Cliente conectado: {addr}")
    conn.sendall("¡Bienvenido al servidor de prueba!".encode("utf-8"))

    try:
        while True:
            datos = conn.recv(4096)
            if not datos:
                break
            mensaje = datos.decode("utf-8")
            print(f"[{addr}] {mensaje}")
            # Eco: reenviar el mensaje al cliente
            respuesta = f"Eco: {mensaje}"
            conn.sendall(respuesta.encode("utf-8"))
    except (ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        print(f"[-] Cliente desconectado: {addr}")
        conn.close()


def main():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("0.0.0.0", 5000))
    servidor.listen(5)
    print("[*] Servidor escuchando en 0.0.0.0:5000")

    try:
        while True:
            conn, addr = servidor.accept()
            hilo = threading.Thread(target=manejar_cliente, args=(conn, addr))
            hilo.daemon = True
            hilo.start()
    except KeyboardInterrupt:
        print("\n[*] Servidor detenido.")
    finally:
        servidor.close()


if __name__ == "__main__":
    main()
```

### Para probar:

1. En una terminal: `python servidor_prueba.py`
2. En otra terminal: `python client.py`

---

## 🧩 Explicación de la Bidireccionalidad

### ¿Por qué necesitamos threads?

Sin threads, el programa se ve así:

```python
# ❌ SIN THREADS - Secuencial (NO funciona correctamente)
while True:
    mensaje = input()          # Bloqueado aquí esperando input
    socket.send(mensaje)
    respuesta = socket.recv()  # Bloqueado aquí esperando respuesta
    print(respuesta)
```

El problema es que `input()` y `recv()` son **bloqueantes**: el programa se
detiene hasta que completen. Esto significa que no puedes recibir mensajes
mientras estás escribiendo.

### Solución con Threads

```python
# ✓ CON THREADS - Simultáneo (bidireccional)

# Thread 1: Emisor
def enviar():
    while activo:
        mensaje = input()       # Bloqueante, pero solo en este thread
        socket.send(mensaje)

# Thread 2: Receptor
def recibir():
    while activo:
        datos = socket.recv()   # Bloqueante, pero solo en este thread
        print(datos)

# Ambos se ejecutan al mismo tiempo
Thread(target=enviar).start()
Thread(target=recibir).start()
```

Cada thread se bloquea de forma **independiente**, permitiendo que el otro
siga funcionando. Así se logra la **comunicación bidireccional simultánea**.

### Diagrama de Flujo

```
INICIO
  │
  ├── Solicitar IP, Puerto, Nombre
  ├── Crear Socket TCP
  ├── Conectar al Servidor
  │
  ├── Crear Evento de Sincronización
  │
  ├── Iniciar Thread Receptor ──┐
  │                             │ (ejecutándose en paralelo)
  ├── Iniciar Thread Emisor ────┤
  │                             │
  ├── Esperar fin de threads ───┘
  │
  ├── Cerrar Conexión
  │
  FIN
```

---

## ⚠️ Manejo de Errores

| Error                        | Causa                        | Respuesta del cliente         |
| ---------------------------- | ---------------------------- | ----------------------------- |
| `ConnectionRefusedError`     | Servidor no disponible       | Mensaje + cierre del cliente  |
| `ConnectionResetError`       | Servidor se desconectó       | Mensaje + cierre del hilo     |
| `ConnectionAbortedError`     | Conexión abortada            | Mensaje + cierre del hilo     |
| `socket.timeout`             | Tiempo de espera agotado     | Mensaje + cierre del cliente  |
| `BrokenPipeError`            | Error al enviar              | Mensaje + cierre del hilo     |
| `KeyboardInterrupt`          | Ctrl+C                       | Cierre limpio                 |

---

## 📝 Librerías Utilizadas

Todas son parte de la **librería estándar** de Python (no requieren instalación):

| Librería      | Uso                                        |
| ------------- | ------------------------------------------ |
| `socket`      | Crear y gestionar conexiones TCP           |
| `threading`   | Ejecutar envío y recepción simultáneamente |
| `sys`         | Salir del programa en caso de error        |
| `time`        | Pausas y espera de threads                 |

---

## 👤 Autor

Proyecto de práctica — Sistemas Distribuidos
