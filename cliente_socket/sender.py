"""
sender.py - Módulo emisor de mensajes

Este módulo se encarga de:
- Leer mensajes del usuario desde la terminal
- Enviar los mensajes al servidor
- Detectar el comando /salir para cerrar la conexión

Se ejecuta en un thread independiente para no bloquear la recepción.
"""


def enviar_mensajes(cliente_socket, evento_activo, nombre_usuario="Cliente"):
    """
    Lee mensajes del usuario desde la terminal y los envía al servidor.

    Esta función está diseñada para ejecutarse en un thread independiente.
    Se mantiene en un bucle mientras el evento 'evento_activo' esté activo (set).

    Args:
        cliente_socket (socket.socket): El socket conectado al servidor.
        evento_activo (threading.Event): Evento que indica si el cliente
                                         sigue activo. Cuando se limpia (clear),
                                         el hilo emisor termina.
        nombre_usuario (str): Nombre del usuario para prefijo de mensajes.
                              Por defecto es "Cliente".

    Funcionamiento:
        1. Lee input del usuario
        2. Si el mensaje es '/salir', cierra la conexión
        3. Si no, envía el mensaje con el prefijo del nombre de usuario
        4. Si ocurre un error de conexión, termina el hilo
    """
    print("\n" + "=" * 50)
    print("  ¡Conexión establecida!")
    print("  Escribe tus mensajes y presiona Enter para enviar.")
    print("  Escribe /salir para desconectarte.")
    print("=" * 50 + "\n")

    while evento_activo.is_set():
        try:
            # input() es BLOQUEANTE: espera a que el usuario escriba algo
            mensaje = input("")

            # Verificar si la conexión sigue activa antes de enviar
            if not evento_activo.is_set():
                break

            # Comando para cerrar la conexión
            if mensaje.strip().lower() == "/salir":
                print("[INFO] Desconectando del servidor...")
                evento_activo.clear()  # Señalar que el cliente quiere salir
                break

            # No enviar mensajes vacíos
            if not mensaje.strip():
                continue

            # Formatear mensaje con el nombre de usuario como prefijo
            mensaje_formateado = f"{nombre_usuario}: {mensaje}"

            # Enviar mensaje codificado en UTF-8
            cliente_socket.sendall(mensaje_formateado.encode("utf-8"))

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # El servidor cerró la conexión
            print("\n[!] Error enviando mensaje: conexión perdida.")
            evento_activo.clear()
            break

        except OSError:
            # Error general de socket
            if evento_activo.is_set():
                print("\n[!] Error de red al enviar mensaje.")
            evento_activo.clear()
            break

        except EOFError:
            # Se cerró la entrada estándar (Ctrl+D en Linux, Ctrl+Z en Windows)
            print("\n[INFO] Entrada cerrada. Desconectando...")
            evento_activo.clear()
            break
