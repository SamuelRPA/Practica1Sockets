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
#  CREATE TABLE IF NOT EXISTS Nodes (
#      id           INT           NOT NULL AUTO_INCREMENT,
#      identifier   VARCHAR(64)   NOT NULL UNIQUE,   -- 'oruro', 'lapaz' ...
#      display_name VARCHAR(128)  DEFAULT NULL,
#      status       VARCHAR(32)   NOT NULL DEFAULT 'Activo',
#      PRIMARY KEY (id),
#      INDEX idx_identifier (identifier)
#  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
#
#  CREATE TABLE IF NOT EXISTS Metrics (
#      id             BIGINT  NOT NULL AUTO_INCREMENT,
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
