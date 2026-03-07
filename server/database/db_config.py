"""
server/database/db_config.py
Configuración de conexión a MySQL.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTA PARA EL EQUIPO DE BASE DE DATOS:
  Complete los valores de DB_HOST, DB_USER, DB_PASSWORD y DB_NAME
  con las credenciales reales de su instancia MySQL.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Credenciales MySQL ─────────────────────────────────────────────────────────
DB_HOST: str = "localhost"          # Host del servidor MySQL
DB_PORT: int = 3306                 # Puerto MySQL (defecto: 3306)
DB_USER: str = "cns_user"          # Usuario de la base de datos
DB_PASSWORD: str = "changeme"      # Contraseña — reemplazar en producción
DB_NAME: str = "storage_cluster"   # Nombre de la base de datos

# ── Pool de conexiones ─────────────────────────────────────────────────────────
POOL_NAME: str = "cns_pool"
POOL_SIZE: int = 5                  # Conexiones simultáneas máximas

# ── Reintentos ────────────────────────────────────────────────────────────────
CONNECTION_RETRIES: int = 3         # Intentos antes de abortar
RETRY_DELAY_SECONDS: float = 2.0   # Espera entre reintentos

# ─────────────────────────────────────────────────────────────────────────────
# Esquema SQL esperado (referencia para el equipo de DB):
#
#  CREATE TABLE metricas (
#      id              BIGINT AUTO_INCREMENT PRIMARY KEY,
#      nodo            VARCHAR(64)   NOT NULL,
#      ip_origen       VARCHAR(45)   DEFAULT NULL,
#      mac_origen      VARCHAR(17)   DEFAULT NULL,
#      timestamp       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
#      disco_nombre    VARCHAR(64)   DEFAULT NULL,
#      disco_tipo      VARCHAR(16)   DEFAULT NULL,   -- HDD | SSD | NVMe
#      disco_total_gb  FLOAT         DEFAULT NULL,
#      disco_usado_gb  FLOAT         DEFAULT NULL,
#      disco_libre_gb  FLOAT         DEFAULT NULL,
#      disco_iops      INT           DEFAULT NULL,
#      ram_total_gb    FLOAT         DEFAULT NULL,
#      ram_usado_gb    FLOAT         DEFAULT NULL,
#      ram_libre_gb    FLOAT         DEFAULT NULL,
#      ram_porcentaje  FLOAT         DEFAULT NULL,   -- 0.0 a 100.0
#      estado          VARCHAR(32)   NOT NULL DEFAULT 'Activo',
#      INDEX idx_nodo      (nodo),
#      INDEX idx_timestamp (timestamp),
#      INDEX idx_ip        (ip_origen),
#      INDEX idx_mac       (mac_origen)
#  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
# ─────────────────────────────────────────────────────────────────────────────
