"""
server/services/metrics_consolidator.py
Lógica de consolidación de métricas del cluster.

Ahora trabaja con el payload aplanado proveniente de socket_server._validate_and_extract():
  nodo, ip_origen, mac_origen, estado,
  disco_nombre, disco_tipo, disco_total_gb, disco_usado_gb, disco_libre_gb, disco_iops,
  ram_total_gb, ram_usado_gb, ram_libre_gb, ram_porcentaje

Calcula:
  Capacity_Total = Σ disco_total_gb
  Free_Total     = Σ disco_libre_gb
  Used_Total     = Σ disco_usado_gb
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
        "Consolidado | nodo='%s' | disco_libre=%.2fGB | ram=%.1f%%",
        nodo,
        payload.get("disco_libre_gb", 0.0),
        payload.get("ram_porcentaje", 0.0),
    )

    # Persistencia en DB (en thread pool para no bloquear asyncio)
    if _db_save_callback:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: _db_save_callback(
                    nodo=payload["nodo"],
                    ip_origen=payload["ip_origen"],
                    mac_origen=payload["mac_origen"],
                    disco_nombre=payload["disco_nombre"],
                    disco_tipo=payload["disco_tipo"],
                    disco_total_gb=payload["disco_total_gb"],
                    disco_usado_gb=payload["disco_usado_gb"],
                    disco_libre_gb=payload["disco_libre_gb"],
                    disco_iops=payload["disco_iops"],
                    ram_total_gb=payload["ram_total_gb"],
                    ram_usado_gb=payload["ram_usado_gb"],
                    ram_libre_gb=payload["ram_libre_gb"],
                    ram_porcentaje=payload["ram_porcentaje"],
                    estado=payload.get("estado", "Activo"),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al persistir métricas del nodo '%s': %s", nodo, exc)


def get_cluster_totals() -> dict[str, Any]:
    """
    Calcula los totales del cluster a partir de los últimos datos en memoria.

    Returns:
        {
          "capacity_total": float,   # Σ disco_total_gb
          "free_total":     float,   # Σ disco_libre_gb
          "used_total":     float,   # Σ disco_usado_gb
          "node_count":     int,
        }
    """
    capacity_total = sum(v.get("disco_total_gb", 0.0) for v in _node_metrics.values())
    free_total     = sum(v.get("disco_libre_gb", 0.0) for v in _node_metrics.values())
    used_total     = sum(v.get("disco_usado_gb", 0.0) for v in _node_metrics.values())

    logger.debug(
        "Totales cluster | nodos=%d | capacity=%.2f | free=%.2f | used=%.2f",
        len(_node_metrics), capacity_total, free_total, used_total,
    )
    return {
        "capacity_total": capacity_total,
        "free_total":     free_total,
        "used_total":     used_total,
        "node_count":     len(_node_metrics),
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
