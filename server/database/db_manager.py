"""
server/database/db_manager.py
Gestor de la base de datos MySQL para el CNS Server.

Tabla objetivo: metricas
Campos: nodo, ip_origen, mac_origen, timestamp, disco_nombre, disco_tipo,
        disco_total_gb, disco_usado_gb, disco_libre_gb, disco_iops,
        ram_total_gb, ram_usado_gb, ram_libre_gb, ram_porcentaje, estado

Índices: idx_nodo, idx_timestamp, idx_ip, idx_mac
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
        """Intenta crear el pool de conexiones con reintentos."""
        for attempt in range(1, cfg.CONNECTION_RETRIES + 1):
            try:
                self._pool = pooling.MySQLConnectionPool(
                    pool_name=cfg.POOL_NAME,
                    pool_size=cfg.POOL_SIZE,
                    host=cfg.DB_HOST,
                    port=cfg.DB_PORT,
                    user=cfg.DB_USER,
                    password=cfg.DB_PASSWORD,
                    database=cfg.DB_NAME,
                    autocommit=True,
                )
                logger.info(
                    "Pool MySQL creado correctamente (host=%s, db=%s).",
                    cfg.DB_HOST, cfg.DB_NAME,
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
        nodo: str,
        ip_origen: str,
        mac_origen: str,
        disco_nombre: str,
        disco_tipo: str,
        disco_total_gb: float,
        disco_usado_gb: float,
        disco_libre_gb: float,
        disco_iops: int,
        ram_total_gb: float,
        ram_usado_gb: float,
        ram_libre_gb: float,
        ram_porcentaje: float,
        estado: str = "Activo",
    ) -> bool:
        """
        Inserta una fila en la tabla 'metricas'.

        Args:
            nodo:           Identificador del nodo (ej: 'nodo-norte-01').
            ip_origen:      Dirección IP del nodo.
            mac_origen:     Dirección MAC del nodo.
            disco_nombre:   Nombre del dispositivo de disco (ej: '/dev/sda').
            disco_tipo:     Tipo de disco (ej: 'HDD', 'SSD').
            disco_total_gb: Capacidad total del disco en GB.
            disco_usado_gb: Espacio usado del disco en GB.
            disco_libre_gb: Espacio libre del disco en GB.
            disco_iops:     IOPS del disco.
            ram_total_gb:   RAM total en GB.
            ram_usado_gb:   RAM usada en GB.
            ram_libre_gb:   RAM libre en GB.
            ram_porcentaje: Porcentaje de uso de RAM (0–100).
            estado:         Estado del nodo (defecto 'Activo').

        Returns:
            True si la inserción fue exitosa, False en caso contrario.
        """
        conn = self._get_connection()
        if conn is None:
            logger.warning(
                "save_metrics: sin conexión DB (nodo=%s). Datos no persistidos.", nodo
            )
            return False

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metricas (
                    nodo, ip_origen, mac_origen, timestamp,
                    disco_nombre, disco_tipo,
                    disco_total_gb, disco_usado_gb, disco_libre_gb, disco_iops,
                    ram_total_gb, ram_usado_gb, ram_libre_gb, ram_porcentaje,
                    estado
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
                """,
                (
                    nodo, ip_origen, mac_origen, datetime.utcnow(),
                    disco_nombre, disco_tipo,
                    disco_total_gb, disco_usado_gb, disco_libre_gb, disco_iops,
                    ram_total_gb, ram_usado_gb, ram_libre_gb, ram_porcentaje,
                    estado,
                ),
            )
            logger.debug(
                "Métricas guardadas | nodo=%s | ip=%s | disco=%.2fGB libre | ram=%.1f%%",
                nodo, ip_origen, disco_libre_gb, ram_porcentaje,
            )
            return True

        except Error as exc:
            logger.error("Error en save_metrics (nodo=%s): %s", nodo, exc)
            return False
        finally:
            cursor.close()
            conn.close()

    # ── update_node_status ────────────────────────────────────────────────────

    def update_node_status(self, nodo: str, status: str) -> bool:
        """
        Inserta una fila de estado en 'metricas' marcando el nodo con el nuevo
        estado y dejando los campos de métricas en NULL para indicar que es un
        registro de estado, no de medición.

        Args:
            nodo:   Identificador del nodo.
            status: Nuevo estado (ej: 'Activo', 'No Reporta', 'Reiniciando').

        Returns:
            True si la inserción fue exitosa, False en caso contrario.
        """
        conn = self._get_connection()
        if conn is None:
            logger.warning("update_node_status: sin conexión DB (nodo=%s).", nodo)
            return False

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metricas (
                    nodo, ip_origen, mac_origen, timestamp,
                    disco_nombre, disco_tipo,
                    disco_total_gb, disco_usado_gb, disco_libre_gb, disco_iops,
                    ram_total_gb, ram_usado_gb, ram_libre_gb, ram_porcentaje,
                    estado
                ) VALUES (
                    %s, NULL, NULL, %s,
                    NULL, NULL,
                    NULL, NULL, NULL, NULL,
                    NULL, NULL, NULL, NULL,
                    %s
                )
                """,
                (nodo, datetime.utcnow(), status),
            )
            logger.info("Estado de nodo '%s' registrado como '%s'.", nodo, status)
            return True

        except Error as exc:
            logger.error(
                "Error en update_node_status (nodo=%s): %s", nodo, exc
            )
            return False
        finally:
            cursor.close()
            conn.close()

    # ── get_cluster_summary ───────────────────────────────────────────────────

    def get_cluster_summary(self) -> dict:
        """
        Retorna un resumen del cluster con la última métrica por nodo.

        Returns:
            {
              "nodes": [{"nodo": str, "ip_origen": str, "mac_origen": str,
                         "disco_total_gb": float, "disco_libre_gb": float,
                         "disco_iops": int, "ram_total_gb": float,
                         "ram_porcentaje": float, "estado": str,
                         "timestamp": str}, ...],
              "capacity_total": float,  # Σ disco_total_gb
              "free_total":     float,  # Σ disco_libre_gb
              "used_total":     float,  # Σ disco_usado_gb
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
            # Obtener la última fila por nodo (usando la clave primaria AUTO_INCREMENT
            # o el timestamp más reciente)
            cursor.execute(
                """
                SELECT m.*
                FROM metricas m
                INNER JOIN (
                    SELECT nodo, MAX(timestamp) AS max_ts
                    FROM metricas
                    GROUP BY nodo
                ) AS latest
                    ON m.nodo = latest.nodo AND m.timestamp = latest.max_ts
                ORDER BY m.nodo
                """
            )
            rows = cursor.fetchall()

            capacity_total = sum((r["disco_total_gb"] or 0) for r in rows)
            free_total = sum((r["disco_libre_gb"] or 0) for r in rows)
            used_total = sum((r["disco_usado_gb"] or 0) for r in rows)

            for row in rows:
                if row.get("timestamp"):
                    row["timestamp"] = row["timestamp"].isoformat()

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
