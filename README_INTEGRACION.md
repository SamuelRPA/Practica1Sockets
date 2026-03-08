# README de Integración — CNS Server (Central Monitoring Server)

> **Versión:** 3.0 | **Puerto:** `5000` | **Protocolo:** TCP + JSON (UTF-8, newline-delimited `\n`)

---

## 1. Para el Equipo de Clientes (Nodos Regionales)

### Conexión

```
HOST: <IP_del_servidor_CNS>
PORT: 5000
```

### ⚠️ IMPORTANTE — Nombre del Nodo (`nodo`)

El campo `nodo` del JSON se usa directamente como `identifier` en la tabla `Nodes` de la base de datos.

**Reglas obligatorias:**
- ✅ Minúsculas
- ✅ Sin espacios ni caracteres especiales
- ✅ Estable (no cambiar una vez registrado; es la clave en la tabla)

| ✅ Correcto      | ❌ Incorrecto          |
|-----------------|----------------------|
| `"oruro"`       | `"Oruro"`            |
| `"lapaz"`       | `"La Paz"`           |
| `"santacruz"`   | `"Santa Cruz"`       |
| `"cochabamba"`  | `"Cochabamba_Node"`  |

---

### Formato del Mensaje de Métricas (Nodo → Servidor)

Envía **un JSON por línea** (`\n` como terminador), codificado en **UTF-8**:

```json
{
  "nodo":           "oruro",
  "ip_origen":      "192.168.1.10",
  "mac_origen":     "AA:BB:CC:DD:EE:FF",
  "display_name":   "Oruro Regional",
  "uptime_seconds": 86400,
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
    "libre_gb":       5.8,
    "porcentaje_uso": 63.75
  },
  "estado": "Activo"
}
```

| Ruta JSON             | Tipo     | Req. | Descripción                                                |
|-----------------------|----------|------|------------------------------------------------------------|
| `nodo`                | `string` | ✅   | ID único del nodo — **minúsculas sin espacios**            |
| `ip_origen`           | `string` | ⬜   | IP del nodo (IPv4)                                         |
| `mac_origen`          | `string` | ⬜   | MAC del adaptador (`XX:XX:XX:XX:XX:XX`)                    |
| `display_name`        | `string` | ⬜   | Nombre legible; si se omite se usa el valor de `nodo`      |
| `uptime_seconds`      | `int`    | ⬜   | Uptime en segundos; si se omite se envía `0`               |
| `disco.nombre`        | `string` | ✅   | Dispositivo (ej: `/dev/sda`, `C:`)                         |
| `disco.tipo`          | `string` | ✅   | `HDD` \| `SSD` \| `NVMe`                                   |
| `disco.total_gb`      | `float`  | ✅   | Capacidad total en GB                                      |
| `disco.usado_gb`      | `float`  | ✅   | Espacio usado en GB                                        |
| `disco.libre_gb`      | `float`  | ✅   | Espacio libre en GB                                        |
| `disco.iops`          | `int`    | ✅   | Operaciones de E/S por segundo                             |
| `ram.total_gb`        | `float`  | ✅   | RAM total en GB                                            |
| `ram.usado_gb`        | `float`  | ⬜   | RAM usada en GB                                            |
| `ram.libre_gb`        | `float`  | ⬜   | RAM libre en GB                                            |
| `ram.porcentaje_uso`  | `float`  | ⬜   | Porcentaje de uso RAM (0.0–100.0)                          |
| `estado`              | `string` | ⬜   | Opcional. Defecto: `"Activo"`                              |

### Respuesta del Servidor (ACK)

```json
{"status": "OK", "nodo": "oruro", "ts": "2026-03-08T04:10:00.000000"}
```

### Comandos que puede recibir el nodo (Servidor → Nodo)

El servidor puede enviar órdenes. El cliente **debe escuchar** mensajes entrantes:

```json
{
  "tipo":       "comando",
  "comando":    "RESCAN",
  "timestamp":  "2026-03-08T04:10:00.000000",
  "origen":     "admin@dashboard",
  "mensaje":    "Ejecutar RESCAN en oruro",
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
            "nodo": "oruro",              # ← minúsculas, sin espacios
            "ip_origen": "192.168.1.10",
            "mac_origen": "AA:BB:CC:DD:EE:FF",
            "display_name": "Oruro Regional",
            "uptime_seconds": 86400,
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
DB_NAME     = "storage_cluster"  # ← nombre de la base de datos
```

### Tablas esperadas — base de datos `storage_cluster`

El servidor **no crea las tablas**; las crea el equipo de DB. El servidor solo llama al SP y hace un UPDATE.

#### Tabla `Nodes`

```sql
CREATE TABLE IF NOT EXISTS Nodes (
    id           INT           NOT NULL AUTO_INCREMENT,
    identifier   VARCHAR(64)   NOT NULL UNIQUE,   -- ej: 'oruro', 'lapaz'
    display_name VARCHAR(128)  DEFAULT NULL,
    status       VARCHAR(32)   NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id),
    INDEX idx_identifier (identifier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Tabla `Metrics`

```sql
CREATE TABLE IF NOT EXISTS Metrics (
    id             BIGINT  NOT NULL AUTO_INCREMENT,
    identifier     VARCHAR(64)  NOT NULL,
    total_gb       FLOAT        DEFAULT NULL,
    used_gb        FLOAT        DEFAULT NULL,
    free_gb        FLOAT        DEFAULT NULL,
    iops           INT          DEFAULT NULL,
    disk_name      VARCHAR(64)  DEFAULT NULL,
    disk_type      VARCHAR(16)  DEFAULT NULL,   -- HDD | SSD | NVMe
    ram_gb         FLOAT        DEFAULT NULL,
    uptime_seconds INT          DEFAULT 0,
    recorded_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_identifier (identifier),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Stored Procedure esperado

```sql
DELIMITER $$
CREATE PROCEDURE sp_InsertMetricAndUpdateNode(
    IN p_identifier     VARCHAR(64),
    IN p_display_name   VARCHAR(128),
    IN p_total_gb       FLOAT,
    IN p_used_gb        FLOAT,
    IN p_free_gb        FLOAT,
    IN p_iops           INT,
    IN p_disk_name      VARCHAR(64),
    IN p_disk_type      VARCHAR(16),
    IN p_ram_gb         FLOAT,
    IN p_uptime_seconds INT
)
BEGIN
    INSERT INTO Metrics (identifier, total_gb, used_gb, free_gb, iops,
                         disk_name, disk_type, ram_gb, uptime_seconds)
    VALUES (p_identifier, p_total_gb, p_used_gb, p_free_gb, p_iops,
            p_disk_name, p_disk_type, p_ram_gb, p_uptime_seconds);

    INSERT INTO Nodes (identifier, display_name, status)
    VALUES (p_identifier, p_display_name, 'Activo')
    ON DUPLICATE KEY UPDATE
        display_name = IF(p_display_name IS NOT NULL, p_display_name, display_name),
        status       = 'Activo';
END$$
DELIMITER ;
```

### Usuario MySQL recomendado

```sql
CREATE USER 'cns_user'@'%' IDENTIFIED BY 'changeme';
GRANT SELECT, INSERT, UPDATE, EXECUTE
    ON storage_cluster.* TO 'cns_user'@'%';
FLUSH PRIVILEGES;
```

### Métodos del `DBManager` y su operación

| Método                              | Operación SQL                                                |
|-------------------------------------|--------------------------------------------------------------|
| `save_metrics(identifier, ...)`     | `CALL sp_InsertMetricAndUpdateNode(?,?,?,?,?,?,?,?,?,?)`     |
| `update_node_status(identifier, s)` | `UPDATE Nodes SET status = ? WHERE identifier = ?`           |
| `get_cluster_summary()`             | Subconsulta de último registro por `identifier` en `Metrics` |

### Acción del Monitor de Fallos

Cuando un nodo no reporta por más de 30 segundos, el servidor ejecuta:

```sql
UPDATE Nodes SET status = 'No Reporta' WHERE identifier = 'oruro';
```

---

## 3. Para el Equipo de Dashboard (Frontend)

### Importar funciones de servicio

```python
from server.services.metrics_consolidator import (
    get_cluster_totals,    # Totales Σ del cluster (en memoria)
    get_all_node_metrics,  # Métricas individuales por nodo
    get_node_metrics,      # Métricas de un nodo específico
)

totals = get_cluster_totals()
# {
#   "capacity_total": 1500.0,  # Σ total_gb (disco)
#   "free_total":      750.5,  # Σ free_gb (disco)
#   "used_total":      749.5,  # Σ used_gb (disco)
#   "node_count":      3
# }

all_nodes = get_all_node_metrics()
# {
#   "oruro": {
#     "identifier": "oruro", "display_name": "Oruro Regional",
#     "total_gb": 500.0, "free_gb": 179.5, "iops": 4200,
#     "ram_gb": 16.0, "uptime_seconds": 86400, "estado": "Activo",
#     "ts": "2026-03-08T04:10:00"
#   }, ...
# }
```

### Alertas de nodos inactivos

```python
from server.services.failure_monitor import get_flagged_nodes
flagged = get_flagged_nodes()
# ["oruro", "lapaz"]
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

---

## 4. Arranque del Servidor

```bash
pip install -r requirements.txt
# Completar server/database/db_config.py con credenciales
# Crear tablas Nodes y Metrics + SP en MySQL (sección 2)
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
  {"nodo": "oruro", "disco": {...}, "ram": {...}}
                                        │
                              _validate_and_extract()
                              (normaliza nodo → identifier)
                                        │
                       ┌────────────────┴──────────────────┐
                       ▼                                    ▼
           metrics_consolidator              db_manager.save_metrics()
           (Σ en memoria RAM)               CALL sp_InsertMetricAndUpdateNode(
               │                               identifier, display_name,
               │                               total_gb, used_gb, free_gb,
               │                               iops, disk_name, disk_type,
               │                               ram_gb, uptime_seconds)
               │                                    │
               │                             INSERT INTO Metrics
               │                             INSERT/UPDATE Nodes (status='Activo')
               │
           failure_monitor (cada 5s)
           → si nodo inactivo > 30s:
             UPDATE Nodes SET status = 'No Reporta'
             WHERE identifier = 'oruro'
```
