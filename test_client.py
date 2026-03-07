import socket
import json
import time

def simular_envio_regional(nombre_nodo):
    # Configuración del cliente
    HOST = '127.0.0.1'  # IP de tu propia máquina (localhost)
    PORT = 5000         # El puerto que abriste en el servidor

    try:
        # 1. Crear el socket y conectar
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print(f"✅ Conectado al Servidor CNS para el nodo: {nombre_nodo}")

            # 2. Preparar el JSON de métricas
            data = {
                "nodo": nombre_nodo,
                "ip_origen": "192.168.10.50",
                "mac_origen": "00:1A:2B:3C:4D:5E",
                "disco": {
                    "nombre": "/dev/sda1",
                    "tipo": "SSD",
                    "total_gb": 1024.0,
                    "usado_gb": 256.5,
                    "libre_gb": 767.5,
                    "iops": 500
                },
                "ram": {
                    "total_gb": 32.0,
                    "usado_gb": 12.4,
                    "libre_gb": 19.6,
                    "porcentaje_uso": 38.75
                }
            }

            # 3. Enviar los datos — IMPORTANTE: terminar con \n para que el servidor
            #    procese el mensaje inmediatamente (asyncio readline)
            mensaje = (json.dumps(data) + "\n").encode('utf-8')
            s.sendall(mensaje)
            print(f"🚀 Métricas enviadas correctamente.")

            # 4. Esperar el ACK del servidor
            respuesta = s.recv(1024)
            print(f"📩 Respuesta del servidor: {respuesta.decode('utf-8')}")

    except Exception as e:
        print(f"❌ Error al conectar: {e}")

if __name__ == "__main__":
    simular_envio_regional("Cochabamba_Regional")