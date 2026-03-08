"""
server/services/metrics_consolidator.py
Lógica de consolidación de métricas del cluster.

Ahora trabaja con el payload aplanado proveniente de socket_server._validate_and_extract().
Campos en uso:
  identifier, display_name, total_gb, used_gb, free_gb, iops,
  disk_name, disk_type, ram_gb, uptime_seconds
  (más alias internos: free_gb_disco, used_gb_disco para los totales en memoria)

Calcula:
  Capacity_Total = Σ total_gb
  Free_Total     = Σ free_gb
  Used_Total     = Σ used_gb_disco
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

from server.utils.logger import get_logger

logger = get_logger("MetricsConsolidator")

# ── Estado en memoria ──────────────────────────────────────────────────────────
# _node_metrics: { nodo -> {payload completo + "ts": datetime} }
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
    Actualiza el estado en memoria y persiste en DB de forma asíncrona.

    Args:
        nodo:    Identificador del nodo.
        payload: Diccionario aplanado devuelto por _validate_and_extract().
    """
    _node_metrics[nodo] = {**payload, "ts": datetime.utcnow()}

    logger.debug(
        "Consolidado | identifier='%s' | free_gb=%.2f | ram_gb=%.2f",
        nodo,
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
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al persistir métricas del nodo '%s': %s", nodo, exc)


def get_cluster_totals(exclude: set = None) -> dict:
    """
    Calcula los totales del cluster a partir de los últimos datos en memoria.
    Los nodos en `exclude` (ej: marcados como 'No Reporta') se omiten del cálculo.

    Args:
        exclude: Conjunto de identifiers a ignorar (defecto: ninguno).

    Returns:
        {
          "capacity_total": float,   # Σ total_gb
          "free_total":     float,   # Σ free_gb
          "used_total":     float,   # Σ used_gb_disco
          "node_count":     int,
        }
    """
    excluded = exclude or set()
    active = {k: v for k, v in _node_metrics.items() if k not in excluded}

    capacity_total = sum(v.get("total_gb",     0.0) for v in active.values())
    free_total     = sum(v.get("free_gb",       0.0) for v in active.values())
    used_total     = sum(v.get("used_gb_disco", 0.0) for v in active.values())

    logger.debug(
        "Totales cluster | nodos=%d (excluidos=%d) | capacity=%.2f | free=%.2f | used=%.2f",
        len(active), len(excluded), capacity_total, free_total, used_total,
    )
    return {
        "capacity_total": capacity_total,
        "free_total":     free_total,
        "used_total":     used_total,
        "node_count":     len(active),
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
