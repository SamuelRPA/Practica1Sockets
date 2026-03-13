"""
server/services/metrics_consolidator.py
Lógica de consolidación de métricas del cluster.

Trabaja con el payload aplanado proveniente de socket_server._validate_and_extract().
Campos en uso:
  identifier, display_name, total_gb, used_gb, free_gb, iops,
  disk_name, disk_type, ram_gb, uptime_seconds, ip_origen, mac_origen

Los totales para el comando STATUS se calculan EN TIEMPO REAL sumando los
valores de socket_server.active_nodes, garantizando que el comando funcione
perfectamente incluso si Railway (MySQL) está desconectado.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

from server.utils.logger import get_logger
import server.network.socket_server as _net   # Importación diferida para evitar círculos

logger = get_logger("MetricsConsolidator")

# ── Estado en memoria local del consolidador ──────────────────────────────────
# _node_metrics se mantiene para retro-compatibilidad con otras partes del código.
# La fuente de verdad para STATUS es _net.active_nodes.
_node_metrics: dict[str, dict] = {}

# Callback para persistir en DB (inyectado por main.py)
_db_save_callback = None    # callable(**kwargs) -> bool


def set_db_callback(callback) -> None:
    """Registra la función de guardado en BD (db_manager.save_metrics)."""
    global _db_save_callback
    _db_save_callback = callback


# ── API principal ──────────────────────────────────────────────────────────────

async def on_metrics_received(
    nodo: str, 
    payload: dict, 
    ip_origen: str = "", 
    mac_origen: str = "",
    total_gb: float = 0,
    used_gb: float = 0,
    free_gb: float = 0,
    iops: int = 0,
    disk_name: str = "",
    disk_type: str = "",
    ram_gb: float = 0,
    ram_usado: float = 0,
    ram_porcentaje: float = 0,
    cantidad_discos: int = 1,
    discos: list = None
) -> None:
    """
    Callback registrado en socket_server.
    Actualiza el estado local en memoria y persiste en DB de forma asíncrona.
    """
    if discos is None:
        discos = []
        
    _node_metrics[nodo] = {
        **payload, 
        "ts": datetime.utcnow(),
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "cantidad_discos": cantidad_discos,
        "discos": discos,
        "ram_usado": ram_usado,
        "ram_porcentaje": ram_porcentaje
    }

    logger.debug(
        "Consolidado | %s | total=%.2f GB | usado=%.2f GB | discos=%d | IP=%s | MAC=%s",
        nodo, total_gb, used_gb, cantidad_discos, ip_origen, mac_origen
    )

    # Persistencia en DB (solo los campos que están en la BD)
    if _db_save_callback:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: _db_save_callback(
                    identifier    = nodo,
                    display_name  = payload.get("display_name", nodo),
                    total_gb      = total_gb,
                    used_gb       = used_gb,
                    free_gb       = free_gb,
                    iops          = iops,
                    disk_name     = disk_name,
                    disk_type     = disk_type,
                    ram_gb        = ram_gb,
                    uptime_seconds= payload.get("uptime_seconds", 0),
                    ip            = ip_origen,
                    mac           = mac_origen
                ),
            )
            logger.info(f"✅ Datos de {nodo} guardados en BD: {total_gb} GB total")
        except Exception as exc:
            logger.error("Error al persistir métricas del nodo '%s': %s", nodo, exc)


def get_cluster_totals(exclude: set = None) -> dict:
    """
    Calcula los totales del cluster en TIEMPO REAL desde socket_server.active_nodes.

    Al leer de active_nodes (que se llena ANTES que la DB), este método funciona
    perfectamente aunque Railway esté desconectado.

    Los nodos en `exclude` (ej: marcados como 'No Reporta') se omiten del cálculo.

    Args:
        exclude: Conjunto de identifiers a ignorar (defecto: ninguno).

    Returns:
        {
          "capacity_total": float,   # Σ total_gb
          "free_total":     float,   # Σ free_gb
          "used_total":     float,   # Σ used_gb
          "node_count":     int,
        }
    """
    excluded = exclude or set()
    # Fuente de verdad: active_nodes del SocketServer (RAM-priority)
    source = {k: v for k, v in _net.active_nodes.items() if k not in excluded}

    capacity_total = sum(v.get("total_gb", 0.0) for v in source.values())
    free_total     = sum(v.get("free_gb",  0.0) for v in source.values())
    used_total     = sum(v.get("used_gb",  0.0) for v in source.values())

    logger.debug(
        "Totales cluster | nodos=%d (excluidos=%d) | capacity=%.2f | free=%.2f | used=%.2f",
        len(source), len(excluded), capacity_total, free_total, used_total,
    )
    return {
        "capacity_total": capacity_total,
        "free_total":     free_total,
        "used_total":     used_total,
        "node_count":     len(source),
    }


def get_node_metrics(nodo: str) -> Optional[dict]:
    """Retorna las últimas métricas en memoria de un nodo específico."""
    entry = _node_metrics.get(nodo)
    if entry:
        return {**entry, "ts": entry["ts"].isoformat()}
    return None


def get_all_node_metrics() -> dict[str, Any]:
    """Retorna todas las métricas en memoria serializadas (para Dashboard)."""
    return {
        nid: {**data, "ts": data["ts"].isoformat()}
        for nid, data in _node_metrics.items()
    }