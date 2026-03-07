# README de Integración — CNS Server (Central Monitoring Server)

> **Versión:** 2.0 | **Puerto:** `5000` | **Protocolo:** TCP + JSON (UTF-8, newline-delimited `\n`)

---

## 1. Para el Equipo de Clientes (Nodos Regionales)

### Conexión

```
HOST: <IP_del_servidor_CNS>
PORT: 5000
```

### Formato del Mensaje de Métricas (Nodo → Servidor)

Envía **un JSON por línea** (`\n` como terminador), codificado en **UTF-8**:

```json
{
  "nodo":       "nodo-norte-01",
  "ip_origen":  "192.168.1.10",
  "mac_origen": "AA:BB:CC:DD:EE:FF",
  "disco": {
    "nombre":   "/dev/sda",
    "tipo":     "SSD",
    "total_gb": 500.0,
    "usado_gb": 320.5,
    "libre_gb": 179.5,
    "iops":     4200
  },
  "ram": {
    "total_gb":      16.0,
    "usado_gb":      10.2,
    "libre_gb":      5.8,
    "porcentaje_uso": 63.75
  },
  "estado": "Activo"
}
```

| Ruta JSON             | Tipo     | Descripción                                      |
|-----------------------|----------|--------------------------------------------------|
| `nodo`                | `string` | ID único y estable del nodo                      |
| `ip_origen`           | `string` | IP del nodo (IPv4)                               |
| `mac_origen`          | `string` | MAC del adaptador (formato `XX:XX:XX:XX:XX:XX`)  |
| `disco.nombre`        | `string` | Dispositivo (ej: `/dev/sda`, `C:`)               |
| `disco.tipo`          | `string` | `HDD` \| `SSD` \| `NVMe`                         |
| `disco.total_gb`      | `float`  | Capacidad total en GB                            |
| `disco.usado_gb`      | `float`  | Espacio usado en GB                              |
| `disco.libre_gb`      | `float`  | Espacio libre en GB                              |
| `disco.iops`          | `int`    | Operaciones de E/S por segundo                  |
| `ram.total_gb`        | `float`  | RAM total en GB                                  |
| `ram.usado_gb`        | `float`  | RAM usada en GB                                  |
| `ram.libre_gb`        | `float`  | RAM libre en GB                                  |
| `ram.porcentaje_uso`  | `float`  | Porcentaje de uso RAM (0.0–100.0)                |
| `estado`              | `string` | Opcional. Defecto: `"Activo"`                    |

### Respuesta del Servidor (ACK)

```json
{"status": "OK", "nodo": "nodo-norte-01", "ts": "2026-03-07T16:25:00.000000"}
```

### Comandos que puede recibir el nodo (Servidor → Nodo)

El servidor puede enviar órdenes. El cliente **debe escuchar** mensajes entrantes en un hilo o corutina separada:

```json
{
  "tipo":       "comando",
  "comando":    "RESCAN",
  "timestamp":  "2026-03-07T16:25:00.000000",
  "origen":     "admin@dashboard",
  "mensaje":    "Ejecutar RESCAN en nodo-norte-01",
  "id_mensaje": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Campo        | Descripción                                  |
|--------------|----------------------------------------------|
| `tipo`       | Siempre `"comando"`                          |
| `comando`    | `RESCAN` \| `REBOOT` \| (otros a definir)    |
| `timestamp`  | Momento ISO 8601 en UTC                      |
| `origen`     | Emisor del comando (`"admin@dashboard"`)     |
| `mensaje`    | Descripción legible del comando              |
| `id_mensaje` | UUID v4 único por envío (para trazabilidad)  |

### Ejemplo mínimo de cliente Python

```python
import socket, json, time, threading

HOST, PORT = "192.168.1.100", 5000

def listen(s):
    """Hilo receptor de comandos del servidor."""
    for line in s.makefile("r"):
        msg = json.loads(line.strip())
        if msg.get("tipo") == "comando":
            print(f"[CMD] {msg['comando']} — id={msg['id_mensaje']}")

with socket.create_connection((HOST, PORT)) as s:
    threading.Thread(target=listen, args=(s,), daemon=True).start()
    while True:
        payload = json.dumps({
            "nodo": "nodo-norte-01",
            "ip_origen": "192.168.1.10",
            "mac_origen": "AA:BB:CC:DD:EE:FF",
            "disco": {"nombre": "/dev/sda", "tipo": "SSD",
                      "total_gb": 500.0, "usado_gb": 320.5,
                      "libre_gb": 179.5, "iops": 4200},
            "ram": {"total_gb": 16.0, "usado_gb": 10.2,
                    "libre_gb": 5.8, "porcentaje_uso": 63.75},
            "estado": "Activo"
        }) + "\n"
        s.sendall(payload.encode("utf-8"))
        time.sleep(10)
```

---

## 2. Para el Equipo de Base de Datos (MySQL)

### Credenciales (completar en `server/database/db_config.py`)

```python
DB_HOST     = "localhost"        # ← su host MySQL
DB_PORT     = 3306
DB_USER     = "cns_user"         # ← su usuario
DB_PASSWORD = "changeme"         # ← su contraseña
DB_NAME     = "storage_cluster"  # ← su base de datos
```

### Esquema SQL — tabla `metricas`

```sql
CREATE DATABASE IF NOT EXISTS storage_cluster
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE storage_cluster;

CREATE TABLE IF NOT EXISTS metricas (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    nodo            VARCHAR(64)   NOT NULL,
    ip_origen       VARCHAR(45)   DEFAULT NULL,
    mac_origen      VARCHAR(17)   DEFAULT NULL,
    timestamp       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disco_nombre    VARCHAR(64)   DEFAULT NULL,
    disco_tipo      VARCHAR(16)   DEFAULT NULL,   -- HDD | SSD | NVMe
    disco_total_gb  FLOAT         DEFAULT NULL,
    disco_usado_gb  FLOAT         DEFAULT NULL,
    disco_libre_gb  FLOAT         DEFAULT NULL,
    disco_iops      INT           DEFAULT NULL,
    ram_total_gb    FLOAT         DEFAULT NULL,
    ram_usado_gb    FLOAT         DEFAULT NULL,
    ram_libre_gb    FLOAT         DEFAULT NULL,
    ram_porcentaje  FLOAT         DEFAULT NULL,   -- 0.0 a 100.0
    estado          VARCHAR(32)   NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id),
    INDEX idx_nodo      (nodo),
    INDEX idx_timestamp (timestamp),
    INDEX idx_ip        (ip_origen),
    INDEX idx_mac       (mac_origen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Usuario MySQL recomendado

```sql
CREATE USER 'cns_user'@'%' IDENTIFIED BY 'changeme';
GRANT SELECT, INSERT ON storage_cluster.metricas TO 'cns_user'@'%';
FLUSH PRIVILEGES;
```

### Métodos del `DBManager` y su operación

| Método                                  | SQL ejecutado                                       |
|-----------------------------------------|-----------------------------------------------------|
| `save_metrics(nodo, ip, mac, ...)`      | `INSERT INTO metricas (todos los campos) VALUES ...` |
| `update_node_status(nodo, status)`      | `INSERT INTO metricas` con campos de métrica en NULL y `estado` = nuevo estado |
| `get_cluster_summary()`                 | Subconsulta del último registro por `nodo`           |

---

## 3. Para el Equipo de Dashboard (Frontend)

### Importar funciones de servicio

```python
from server.services.metrics_consolidator import (
    get_cluster_totals,    # Totales Σ del cluster
    get_all_node_metrics,  # Métricas individuales por nodo
    get_node_metrics,      # Métricas de un nodo específico
)

totals = get_cluster_totals()
# {
#   "capacity_total": 1500.0,  # Σ disco_total_gb
#   "free_total":      750.5,  # Σ disco_libre_gb
#   "used_total":      749.5,  # Σ disco_usado_gb
#   "node_count":      3
# }

all_nodes = get_all_node_metrics()
# {
#   "nodo-norte-01": {
#     "nodo": "nodo-norte-01", "ip_origen": "...", "mac_origen": "...",
#     "disco_total_gb": 500.0, "disco_libre_gb": 179.5, "disco_iops": 4200,
#     "ram_total_gb": 16.0, "ram_porcentaje": 63.75, "estado": "Activo",
#     "ts": "2026-03-07T16:25:00"
#   }, ...
# }
```

### Alertas de nodos inactivos

```python
from server.services.failure_monitor import get_flagged_nodes
flagged = get_flagged_nodes()
# ["nodo-sur-02", "nodo-este-01"]
```

### Nodos TCP conectados en tiempo real

```python
from server.network.socket_server import active_clients
connected = list(active_clients.keys())
```

### Resumen completo desde DB

```python
from server.database.db_manager import DBManager
db = DBManager()
summary = db.get_cluster_summary()
# {"nodes": [...], "capacity_total": float, "free_total": float, "used_total": float}
```

### Integración con API REST (ejemplo FastAPI)

```python
from fastapi import FastAPI
from server.services.metrics_consolidator import get_cluster_totals, get_all_node_metrics

app = FastAPI()

@app.get("/api/cluster/totals")
def cluster_totals():
    return get_cluster_totals()

@app.get("/api/cluster/nodes")
def cluster_nodes():
    return get_all_node_metrics()
```

---

## 4. Arranque del Servidor

```bash
pip install -r requirements.txt
# Completar server/database/db_config.py
# Crear la tabla metricas en MySQL (esquema de la sección 2)
python main.py
```

### Consola interactiva (disponible en el terminal al ejecutar)

| Comando             | Descripción                                       |
|---------------------|---------------------------------------------------|
| `LIST`              | Lista nodos TCP conectados                        |
| `STATUS`            | Totales del cluster y nodos sin reporte           |
| `RESCAN <nodo>`     | Envía comando RESCAN al nodo                      |
| `REBOOT <nodo>`     | Envía comando REBOOT al nodo                      |
| `HELP`              | Muestra ayuda                                     |
| `EXIT`              | Detiene el servidor de forma controlada           |

---

## 5. Diagrama de Flujo

```
[Nodo Regional] ──JSON anidado──> socket_server.py
                                        │
                              _validate_and_extract()
                              (aplana disco.* y ram.*)
                                        │
                       ┌────────────────┴──────────────────┐
                       ▼                                   ▼
           metrics_consolidator                  db_manager.save_metrics()
           (Σ en memoria RAM)                    (INSERT INTO metricas)
                       │
           failure_monitor (cada 5s)
           → update_node_status('No Reporta')
           → INSERT INTO metricas (estado=NULL metrics)
```
