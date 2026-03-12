import socket
import json
import time

def test_final():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('127.0.0.1', 5000))
            
            # Formato exacto para el Stored Procedure y el Monitor
            payload = {
    "nodo": "test_local",
    "display_name": "Mi PC de Prueba",
    "timestamp": time.time(),
    "disco": {
        "total_gb": 1024.0,
        "used_gb": 500.0,
        "free_gb": 524.0
    },
    "ram": {
        "total_gb": 16.0,
        "used_gb": 4.0,
        "free_gb": 12.0
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