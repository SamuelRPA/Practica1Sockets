"""
server/database/db_manager.py
Gestor de la base de datos MySQL para el CNS Server.

Base de datos: storage_cluster
Tablas objetivo:
  - Nodes   (identifier, display_name, status, ...)
  - Metrics (identifier, total_gb, used_gb, free_gb, iops,
             disk_name, disk_type, ram_gb, uptime_seconds, recorded_at)

Operaciones principales:
  - save_metrics  → CALL sp_InsertMetricAndUpdateNode(?,?,?,?,?,?,?,?,?,?)
  - update_node_status → UPDATE Nodes SET status = ? WHERE identifier = ?
  - get_cluster_summary → SELECT de la tabla Metrics
"""

import time
from datetime import datetime
from typing import Optional

import mysql.connector
from mysql.connector import Error, pooling

from server.database import db_config as cfg
from server.utils.logger import get_logger

logger = get_logger("DBManager")


class DBManager:
    """
    Gestiona el pool de conexiones MySQL y las operaciones CRUD
    sobre la tabla 'metricas'.
    """

    def __init__(self) -> None:
        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._connect_with_retry()

    # ── Inicialización ─────────────────────────────────────────────────────────

    def _connect_with_retry(self) -> None:
        """Intenta crear el pool de conexiones con reintentos.

        Usa DB_CONFIG para incluir el puerto (46975) y SSL (ssl_disabled=False)
        requeridos por Railway.
        """
        for attempt in range(1, cfg.CONNECTION_RETRIES + 1):
            try:
                self._pool = pooling.MySQLConnectionPool(
                    pool_name=cfg.POOL_NAME,
                    pool_size=cfg.POOL_SIZE,
                    **cfg.DB_CONFIG,         # host, port, user, password, database, ssl_disabled
                    autocommit=True,
                )
                logger.info(
                    "Pool MySQL creado correctamente (host=%s, port=%d, db=%s, ssl=habilitado).",
                    cfg.DB_HOST, cfg.DB_PORT, cfg.DB_NAME,
                )
                return
            except Error as exc:
                logger.warning(
                    "Intento %d/%d de conexión a MySQL fallido: %s",
                    attempt, cfg.CONNECTION_RETRIES, exc,
                )
                if attempt < cfg.CONNECTION_RETRIES:
                    time.sleep(cfg.RETRY_DELAY_SECONDS)

        logger.error(
            "No se pudo conectar a MySQL tras %d intentos. "
            "El servidor funcionará sin persistencia.",
            cfg.CONNECTION_RETRIES,
        )

    def _get_connection(self):
        """Obtiene una conexión del pool (o None si no hay pool)."""
        if self._pool is None:
            return None
        try:
            return self._pool.get_connection()
        except Error as exc:
            logger.error("Error al obtener conexión del pool: %s", exc)
            return None

    # ── save_metrics ──────────────────────────────────────────────────────────

    def save_metrics(
        self,
        identifier: str,
        display_name: str,
        total_gb: float,
        used_gb: float,
        free_gb: float,
        iops: int,
        disk_name: str,
        disk_type: str,
        ram_gb: float,
        uptime_seconds: int = 0,
    ) -> bool:
        """
        Llama al Stored Procedure sp_InsertMetricAndUpdateNode.

        Parámetros (en orden exacto del SP):
            identifier:     ID único del nodo (ej: 'oruro', 'lapaz').
            display_name:   Nombre legible del nodo (ej: 'Oruro').
            total_gb:       Capacidad total del disco en GB.
            used_gb:        Espacio usado del disco en GB.
            free_gb:        Espacio libre del disco en GB.
            iops:           Operaciones de E/S por segundo.
            disk_name:      Nombre del dispositivo (ej: '/dev/sda', 'C:').
            disk_type:      Tipo de disco ('HDD' | 'SSD' | 'NVMe').
            ram_gb:         RAM total en GB.
            uptime_seconds: Uptime del nodo en segundos (defecto 0).

        Returns:
            True si el SP se ejecutó correctamente, False en caso contrario.
        """
        conn = self._get_connection()
        if conn is None:
            logger.warning(
                "save_metrics: sin conexión DB (identifier=%s). Datos no persistidos.",
                identifier,
            )
            return False

        try:
            cursor = conn.cursor()
            cursor.callproc(
                "sp_InsertMetricAndUpdateNode",
                (
                    identifier,
                    display_name,
                    total_gb,
                    used_gb,
                    free_gb,
                    iops,
                    disk_name,
                    disk_type,
                    ram_gb,
                    uptime_seconds,
                ),
            )
            logger.debug(
                "SP ejecutado | identifier=%s | free_gb=%.2f | ram_gb=%.2f",
                identifier, free_gb, ram_gb,
            )
            return True

        except Error as exc:
            logger.error("Error en save_metrics (identifier=%s): %s", identifier, exc)
            return False
        finally:
            cursor.close()
            conn.close()

    # ── update_node_status ────────────────────────────────────────────────────

    def update_node_status(self, identifier: str, status: str) -> bool:
        """
        Actualiza el campo 'status' de un nodo en la tabla Nodes.

        Cuando el monitor de fallos detecta que un nodo dejó de reportar,
        llama a este método con status='No Reporta'.

        Args:
            identifier: Identificador único del nodo (ej: 'oruro').
            status:     Nuevo estado ('No Reporta', 'Activo', etc.).

        Returns:
            True si el UPDATE fue exitoso, False en caso contrario.
        """
        conn = self._get_connection()
        if conn is None:
            logger.warning(
                "update_node_status: sin conexión DB (identifier=%s).", identifier
            )
            return False

        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Nodes SET status = %s WHERE identifier = %s",
                (status, identifier),
            )
            logger.info(
                "Estado del nodo '%s' actualizado a '%s' (%d fila(s) afectada(s)).",
                identifier, status, cursor.rowcount,
            )
            return True

        except Error as exc:
            logger.error(
                "Error en update_node_status (identifier=%s): %s", identifier, exc
            )
            return False
        finally:
            cursor.close()
            conn.close()

    # ── get_cluster_summary ───────────────────────────────────────────────────

    def get_cluster_summary(self) -> dict:
        """
        Retorna un resumen del cluster con la última métrica por nodo,
        consultando la tabla Metrics (nueva estructura).

        Returns:
            {
              "nodes": [{"identifier": str, "display_name": str,
                         "total_gb": float, "used_gb": float, "free_gb": float,
                         "iops": int, "disk_name": str, "disk_type": str,
                         "ram_gb": float, "uptime_seconds": int,
                         "recorded_at": str}, ...],
              "capacity_total": float,  # Σ total_gb
              "free_total":     float,  # Σ free_gb
              "used_total":     float,  # Σ used_gb
            }
        """
        empty = {
            "nodes": [],
            "capacity_total": 0.0,
            "free_total": 0.0,
            "used_total": 0.0,
        }
        conn = self._get_connection()
        if conn is None:
            logger.warning("get_cluster_summary: sin conexión DB.")
            return empty

        try:
            cursor = conn.cursor(dictionary=True)
            # Última métrica por identifier (nodo) de la tabla Metrics
            cursor.execute(
                """
                SELECT m.*
                FROM Metrics m
                INNER JOIN (
                    SELECT identifier, MAX(recorded_at) AS max_ts
                    FROM Metrics
                    GROUP BY identifier
                ) AS latest
                    ON m.identifier = latest.identifier
                    AND m.recorded_at = latest.max_ts
                ORDER BY m.identifier
                """
            )
            rows = cursor.fetchall()

            capacity_total = sum((r["total_gb"] or 0) for r in rows)
            free_total     = sum((r["free_gb"]  or 0) for r in rows)
            used_total     = sum((r["used_gb"]  or 0) for r in rows)

            for row in rows:
                if row.get("recorded_at"):
                    row["recorded_at"] = row["recorded_at"].isoformat()

            logger.debug(
                "Resumen cluster: %d nodos | capacity=%.2f | free=%.2f",
                len(rows), capacity_total, free_total,
            )
            return {
                "nodes": rows,
                "capacity_total": capacity_total,
                "free_total": free_total,
                "used_total": used_total,
            }

        except Error as exc:
            logger.error("Error en get_cluster_summary: %s", exc)
            return empty
        finally:
            cursor.close()
            conn.close()
