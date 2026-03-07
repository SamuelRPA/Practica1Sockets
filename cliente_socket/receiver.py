"""
receiver.py - Módulo receptor de mensajes

Este módulo se encarga de:
- Escuchar mensajes entrantes del servidor
- Imprimir los mensajes recibidos en pantalla
- Detectar desconexiones del servidor

Se ejecuta en un thread independiente para no bloquear el envío.
"""


def recibir_mensajes(cliente_socket, evento_activo):
    """
    Escucha continuamente mensajes del servidor y los muestra en pantalla.

    Esta función está diseñada para ejecutarse en un thread independiente.
    Se mantiene en un bucle mientras el evento 'evento_activo' esté activo (set).

    Args:
        cliente_socket (socket.socket): El socket conectado al servidor.
        evento_activo (threading.Event): Evento que indica si el cliente
                                         sigue activo. Cuando se limpia (clear),
                                         el hilo receptor termina.

    Funcionamiento:
        1. Espera datos del servidor con recv()
        2. Si recibe datos, los decodifica y muestra
        3. Si recv() retorna vacío, significa que el servidor se desconectó
        4. Si ocurre un error de conexión, termina el hilo
    """
    while evento_activo.is_set():
        try:
            # recv(4096) espera hasta recibir datos (máximo 4096 bytes)
            # Esta llamada es BLOQUEANTE: el hilo se queda aquí esperando
            datos = cliente_socket.recv(4096)

            if datos:
                # Decodificar los bytes recibidos a texto (UTF-8)
                mensaje = datos.decode("utf-8")
                # Mostrar el mensaje del servidor con formato claro
                print(f"\n[Servidor]: {mensaje}")
            else:
                # recv() retorna b'' cuando el servidor cierra la conexión
                print("\n[!] El servidor se ha desconectado.")
                evento_activo.clear()  # Señalar que la conexión terminó
                break

        except ConnectionResetError:
            # El servidor cerró la conexión abruptamente
            print("\n[!] Conexión perdida con el servidor.")
            evento_activo.clear()
            break

        except ConnectionAbortedError:
            # La conexión fue abortada (posiblemente por cierre local)
            if evento_activo.is_set():
                print("\n[!] Conexión abortada.")
            evento_activo.clear()
            break

        except OSError:
            # Error general de socket (por ejemplo, socket ya cerrado)
            if evento_activo.is_set():
                print("\n[!] Error de red en la recepción.")
            evento_activo.clear()
            break

    # Mensaje informativo al terminar el hilo receptor
    # (solo visible en modo debug)
