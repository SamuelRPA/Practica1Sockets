"""
server/services/metrics_consolidator.py
Lógica de consolidación de métricas del cluster.

Trabaja con el payload aplanado proveniente de socket_server._validate_and_extract().
Campos en uso:
  identifier, display_name, total_gb, used_gb, free_gb, iops,
  disk_name, disk_type, ram_gb, uptime_seconds

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

async def on_metrics_received(nodo: str, payload: dict) -> None:
    """
    Callback registrado en socket_server.
    Actualiza el estado local en memoria y persiste en DB de forma asíncrona.

    NOTA: socket_server ya guardó el payload en active_nodes ANTES de llamar
    a este callback (prioridad RAM). Aquí sólo mantenemos _node_metrics para
    compatibilidad y lanzamos la persistencia DB.

    Args:
        nodo:    Identificador del nodo.
        payload: Diccionario aplanado devuelto por _validate_and_extract().
    """
    _node_metrics[nodo] = {**payload, "ts": datetime.utcnow()}

    logger.debug(
        "Consolidado | identifier='%s' | used_gb=%.2f | free_gb=%.2f | ram_gb=%.2f",
        nodo,
        payload.get("used_gb", 0.0),
        payload.get("free_gb", 0.0),
        payload.get("ram_gb", 0.0),
    )

    # Persistencia en DB (en thread pool para no bloquear asyncio)
    if _db_save_callback:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: _db_save_callback(
                    identifier    =payload["identifier"],
                    display_name  =payload.get("display_name", payload["identifier"]),
                    total_gb      =payload["total_gb"],
                    used_gb       =payload["used_gb"],
                    free_gb       =payload["free_gb"],
                    iops          =payload["iops"],
                    disk_name     =payload["disk_name"],
                    disk_type     =payload["disk_type"],
                    ram_gb        =payload["ram_gb"],
                    uptime_seconds=payload.get("uptime_seconds", 0),
                    ip            =payload.get("ip_origen", ""),
                    mac           =payload.get("mac_origen", ""),
                ),
            )
        except Exception as exc:  # noqa: BLE001
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

    def _safe_get(entry: dict, key: str, nested_key: str, fallback_key: str = "", default: float = 0.0) -> float:
        try:
            if "disco" in entry and isinstance(entry["disco"], dict) and entry["disco"]:
                val = entry["disco"].get(nested_key, entry["disco"].get(fallback_key))
                if val is not None:
                    return float(val)
            val = entry.get(key, entry.get(fallback_key))
            if val is not None:
                return float(val)
            return float(default)
        except (ValueError, TypeError, AttributeError):
            return float(default)

    capacity_total = sum(_safe_get(v, "total_gb", "total_gb") for v in source.values())
    free_total     = sum(_safe_get(v, "free_gb", "free_gb", fallback_key="libre_gb") for v in source.values())
    used_total     = sum(_safe_get(v, "used_gb", "used_gb", fallback_key="usado_gb") for v in source.values())

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
