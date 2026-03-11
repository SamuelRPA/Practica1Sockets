import socket
import json
import time

def test_final():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('127.0.0.1', 5000))
            
            # Formato exacto para el Stored Procedure y el Monitor
            payload = {
                "nodo": "cochabamba",
                "display_name": "Cochabamba Central",
                "disco": {
                    "nombre": "C:",
                    "tipo": "SSD",
                    "total_gb": 1024.0,
                    "used_gb": 200.0,
                    "free_gb": 824.0,
                    "iops": 400
                },
                "ram": {
                    "total_gb": 16.0,
                    "used_gb": 8.0,
                    "free_gb": 8.0,
                    "uptime_seconds": 3600
                }
            }
            
            s.sendall((json.dumps(payload) + "\n").encode('utf-8'))
            print("🚀 Envío exitoso. Revisa la consola del servidor.")
            print("📩 Respuesta:", s.recv(1024).decode())
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    while True: # Esto mantendrá al cliente enviando datos
        test_final()
        print("⏳ Esperando 30 segundos para el siguiente envío...")
        time.sleep(30)