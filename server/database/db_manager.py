"""
server/database/db_manager.py
Gestor de la base de datos MySQL para el CNS Server.
VERSIÓN CON MÁS LOGS PARA DEPURAR
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import mysql.connector
from mysql.connector import Error, pooling

from server.database import db_config as cfg
from server.utils.logger import get_logger

logger = get_logger("DBManager")


class DBManager:
    """
    Gestiona el pool de conexiones MySQL y las operaciones CRUD
    sobre las tablas 'Nodes' y 'Metrics'.
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
                    **cfg.DB_CONFIG,
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
            "No se pudo conectar a MySQL tras %d intentos. El servidor funcionará sin persistencia.",
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
        ip: str = "",
        mac: str = ""
    ) -> bool:
        """
        Guarda una métrica y actualiza last_seen del nodo, incluyendo IP y MAC.
        """
        # 🔍 LOG DE LO QUE RECIBE
        logger.info(f"🔍 save_metrics RECIBIÓ para {identifier}:")
        logger.info(f"   total_gb={total_gb}, used_gb={used_gb}, free_gb={free_gb}, ram_gb={ram_gb}")
        logger.info(f"   ip={ip}, mac={mac}")
        
        conn = self._get_connection()
        if conn is None:
            logger.error(f"❌ save_metrics: sin conexión DB (identifier={identifier})")
            return False

        try:
            cursor = conn.cursor()
            
            # Verificar si el nodo existe
            cursor.execute("SELECT id FROM Nodes WHERE identifier = %s", (identifier,))
            result = cursor.fetchone()
            
            ahora = datetime.now()

            if result:
                # Nodo existe → ACTUALIZAR
                node_id = result[0]
                cursor.execute("""
                    UPDATE Nodes 
                    SET display_name = %s,
                        disk_name = %s,
                        disk_type = %s,
                        ram_gb = %s,
                        uptime_seconds = %s,
                        ip = %s,
                        mac = %s,
                        status = 'Activo',
                        last_seen = %s
                    WHERE id = %s
                """, (display_name, disk_name, disk_type, ram_gb, uptime_seconds, 
                      ip, mac, ahora, node_id))
                logger.info(f"✅ Nodo {identifier} actualizado")
            else:
                # Nodo nuevo → INSERTAR
                cursor.execute("""
                    INSERT INTO Nodes 
                        (identifier, display_name, disk_name, disk_type, ram_gb, 
                         uptime_seconds, ip, mac, status, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Activo', %s)
                """, (identifier, display_name, disk_name, disk_type, ram_gb, 
                      uptime_seconds, ip, mac, ahora))
                node_id = cursor.lastrowid
                logger.info(f"✅ Nuevo nodo {identifier} creado")

            # Insertar métrica SOLO si hay datos válidos
            if total_gb > 0:
                utilization = (used_gb / total_gb * 100) if total_gb > 0 else 0
                cursor.execute("""
                    INSERT INTO Metrics 
                        (node_id, timestamp, total_capacity_gb, used_space_gb, free_space_gb, 
                         utilization_percentage, iops)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (node_id, ahora, total_gb, used_gb, free_gb, utilization, iops))
                logger.info(f"✅ Métrica insertada para {identifier}: {total_gb} GB")
            else:
                logger.warning(f"⚠️ No se insertó métrica para {identifier}: total_gb={total_gb}")

            conn.commit()
            return True

        except Error as exc:
            logger.error(f"❌ Error en save_metrics (identifier={identifier}): {exc}")
            return False
        finally:
            cursor.close()
            conn.close()

    # ── update_node_status ────────────────────────────────────────────────────

    def update_node_status(self, identifier: str, status: str) -> bool:
        """Actualiza el campo 'status' de un nodo en la tabla Nodes."""
        conn = self._get_connection()
        if conn is None:
            logger.warning(f"update_node_status: sin conexión DB (identifier={identifier})")
            return False

        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Nodes SET status = %s WHERE identifier = %s",
                (status, identifier),
            )
            logger.info(f"✅ Estado del nodo '{identifier}' actualizado a '{status}'")
            return True
        except Error as exc:
            logger.error(f"Error en update_node_status (identifier={identifier}): {exc}")
            return False
        finally:
            cursor.close()
            conn.close()

    # ── get_cluster_summary ───────────────────────────────────────────────────

    def get_cluster_summary(self) -> Dict[str, Any]:
        """Retorna un resumen del cluster con la última métrica por nodo."""
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
            
            cursor.execute("""
                SELECT 
                    n.identifier,
                    n.display_name,
                    n.status,
                    n.last_seen,
                    n.disk_type,
                    n.ram_gb,
                    n.ip,
                    n.mac,
                    m.total_capacity_gb as total_gb,
                    m.used_space_gb as used_gb,
                    m.free_space_gb as free_gb,
                    m.iops,
                    m.timestamp as recorded_at
                FROM Nodes n
                LEFT JOIN Metrics m ON n.id = m.node_id
                AND m.timestamp = (
                    SELECT MAX(timestamp) 
                    FROM Metrics 
                    WHERE node_id = n.id
                )
                ORDER BY n.display_name
            """)
            
            rows = cursor.fetchall()
            
            nodes = []
            capacity_total = 0.0
            used_total = 0.0
            free_total = 0.0

            for row in rows:
                node_data = {
                    "identifier": row["identifier"],
                    "display_name": row["display_name"],
                    "total_gb": float(row["total_gb"] or 0),
                    "used_gb": float(row["used_gb"] or 0),
                    "free_gb": float(row["free_gb"] or 0),
                    "iops": int(row["iops"] or 0),
                    "disk_type": row["disk_type"] or "N/A",
                    "ram_gb": float(row["ram_gb"] or 0),
                    "ip": row["ip"] or "",
                    "mac": row["mac"] or "",
                    "status": row["status"] or "No Reporta",
                    "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    "recorded_at": row["recorded_at"].isoformat() if row["recorded_at"] else None
                }
                
                if row["status"] == "Activo" and row["total_gb"]:
                    capacity_total += float(row["total_gb"])
                    used_total += float(row["used_gb"] or 0)
                    free_total += float(row["free_gb"] or 0)
                
                nodes.append(node_data)

            logger.info(f"📊 get_cluster_summary: {len(nodes)} nodos, capacidad_total={capacity_total} GB")
            return {
                "nodes": nodes,
                "capacity_total": capacity_total,
                "free_total": free_total,
                "used_total": used_total,
            }

        except Error as exc:
            logger.error(f"Error en get_cluster_summary: {exc}")
            return empty
        finally:
            if 'cursor' in locals():
                cursor.close()
            if conn:
                conn.close()

    # ── get_node_history ─────────────────────────────────────────────────────

    def get_node_history(self, identifier: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Obtiene el historial de métricas de un nodo específico."""
        conn = self._get_connection()
        if conn is None:
            logger.warning(f"get_node_history: sin conexión DB (identifier={identifier})")
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    m.timestamp,
                    m.used_space_gb as used_gb,
                    m.total_capacity_gb as total_gb,
                    m.free_space_gb as free_gb,
                    m.utilization_percentage
                FROM Metrics m
                INNER JOIN Nodes n ON m.node_id = n.id
                WHERE n.identifier = %s
                ORDER BY m.timestamp DESC
                LIMIT %s
            """, (identifier, limit))
            
            rows = cursor.fetchall()
            
            for row in rows:
                if row["timestamp"]:
                    row["timestamp"] = row["timestamp"].isoformat()
                    
            return rows

        except Error as exc:
            logger.error(f"Error en get_node_history ({identifier}): {exc}")
            return []
        finally:
            cursor.close()
            conn.close()