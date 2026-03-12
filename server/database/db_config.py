"""
server/database/db_config.py
Configuración de conexión a MySQL (Railway).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTA: Rellene DB_PASSWORD con la contraseña real antes de arrancar.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Credenciales Railway ───────────────────────────────────────────────────────
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

DB_HOST:     str = os.getenv("DB_HOST", "hopper.proxy.rlwy.net")
DB_PORT:     int = int(os.getenv("DB_PORT", "46975"))
DB_USER:     str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")          
DB_NAME:     str = os.getenv("DB_NAME", "storage_cluster")
SSL_MODE:    str = os.getenv("SSL_MODE", "REQUIRED")

# ── Dict completo para el pool de conexiones ─────────────────────────────────
DB_CONFIG: dict = {
    "host":         DB_HOST,
    "port":         DB_PORT,
    "user":         DB_USER,
    "password":     DB_PASSWORD,
    "database":     DB_NAME,
    "ssl_disabled": False,      # SSL habilitado (Railway lo requiere)
}

# ── Pool de conexiones ─────────────────────────────────────────────────────────
POOL_NAME: str   = "cns_pool"
POOL_SIZE: int   = 5           # Conexiones simultáneas máximas

# ── Reintentos ────────────────────────────────────────────────────────────────
CONNECTION_RETRIES:  int   = 3
RETRY_DELAY_SECONDS: float = 2.0

# ─────────────────────────────────────────────────────────────────────────────
# Esquema SQL esperado (referencia para el equipo de DB):
#
#  CREATE TABLE IF NOT EXISTS Nodes (
#      id           INT           NOT NULL AUTO_INCREMENT,
#      identifier   VARCHAR(64)   NOT NULL UNIQUE,   -- 'cochabamba', 'lapaz'...
#      display_name VARCHAR(128)  DEFAULT NULL,
#      status       VARCHAR(32)   NOT NULL DEFAULT 'Activo',
#      PRIMARY KEY (id),
#      INDEX idx_identifier (identifier)
#  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
#
#  CREATE TABLE IF NOT EXISTS Metrics (
#      id             BIGINT       NOT NULL AUTO_INCREMENT,
#      identifier     VARCHAR(64)  NOT NULL,
#      total_gb       FLOAT        DEFAULT NULL,
#      used_gb        FLOAT        DEFAULT NULL,
#      free_gb        FLOAT        DEFAULT NULL,
#      iops           INT          DEFAULT NULL,
#      disk_name      VARCHAR(64)  DEFAULT NULL,
#      disk_type      VARCHAR(16)  DEFAULT NULL,   -- HDD | SSD | NVMe
#      ram_gb         FLOAT        DEFAULT NULL,
#      uptime_seconds INT          DEFAULT 0,
#      recorded_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
#      PRIMARY KEY (id),
#      INDEX idx_identifier (identifier),
#      INDEX idx_recorded_at (recorded_at)
#  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
#
#  Stored Procedure requerido: sp_InsertMetricAndUpdateNode
#  (ver README_INTEGRACION.md sección 2 para el CREATE PROCEDURE completo)
# ─────────────────────────────────────────────────────────────────────────────
