"""
server/services/failure_monitor.py
Tarea de fondo que detecta nodos inactivos.

Lógica:
  - Cada MONITOR_INTERVAL segundos revisa todos los nodos conocidos.
  - Si un nodo no ha reportado en más de NODE_TIMEOUT segundos, se marca
    como 'No Reporta' en la DB y se emite una alerta de log.
  - Si el nodo vuelve a reportar, su estado se restaura a 'Activo'
    (gestionado por metrics_consolidator / db_manager.save_metrics).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from server.utils.logger import get_logger

logger = get_logger("FailureMonitor")

# ── Parámetros configurables ───────────────────────────────────────────────────
MONITOR_INTERVAL: float = 5.0    # segundos entre cada revisión
NODE_TIMEOUT: float = 30.0       # segundos sin reporte → 'No Reporta'

# ── Callbacks externos (inyectados por main.py) ────────────────────────────────
_get_last_seen = None     # callable() -> dict[node_id, datetime]
_update_status = None     # callable(node_id, status) -> bool  (puede ser sync)

# ── Estado interno ────────────────────────────────────────────────────────────
_already_flagged: set[str] = set()   # nodos ya marcados como 'No Reporta'


def set_last_seen_source(fn) -> None:
    """Inyecta la función que devuelve el dict {node_id -> last_seen (UTC)}."""
    global _get_last_seen
    _get_last_seen = fn


def set_status_updater(fn) -> None:
    """
    Inyecta la función para actualizar el estado del nodo.
    Puede ser db_manager.update_node_status (síncrona) o una corutina.
    """
    global _update_status
    _update_status = fn


# ── Tarea principal ────────────────────────────────────────────────────────────

async def monitor_loop() -> None:
    """
    Corutina principal del monitor de fallos.
    Debe ejecutarse como tarea asyncio independiente.

    Flujo por iteración:
      1. Obtiene last_seen de socket_server.
      2. Calcula nodos que superaron NODE_TIMEOUT.
      3. Marca nodos como 'No Reporta' en DB (evitando duplicar alertas).
      4. Elimina de _already_flagged los nodos que volvieron a reportar.
    """
    logger.info(
        "Monitor de fallos iniciado (intervalo=%.1fs, timeout=%.1fs).",
        MONITOR_INTERVAL,
        NODE_TIMEOUT,
    )

    while True:
        await asyncio.sleep(MONITOR_INTERVAL)

        if _get_last_seen is None:
            logger.debug("monitor_loop: sin fuente de last_seen configurada, esperando.")
            continue

        now = datetime.utcnow()
        timeout_delta = timedelta(seconds=NODE_TIMEOUT)
        last_seen_map: dict[str, datetime] = _get_last_seen()

        for node_id, last_ts in last_seen_map.items():
            inactive_seconds = (now - last_ts).total_seconds()

            if inactive_seconds > NODE_TIMEOUT:
                if node_id not in _already_flagged:
                    logger.warning(
                        "ALERTA: Nodo '%s' SIN REPORTE desde hace %.1f segundos — marcando como 'No Reporta'.",
                        node_id,
                        inactive_seconds,
                    )
                    _already_flagged.add(node_id)
                    await _apply_status_update(node_id, "No Reporta")
                else:
                    logger.debug(
                        "Nodo '%s' continúa sin reportar (%.1fs de inactividad).",
                        node_id,
                        inactive_seconds,
                    )
            else:
                # El nodo volvió a reportar; limpiar flag
                if node_id in _already_flagged:
                    logger.info(
                        "Nodo '%s' recuperado tras %.1fs de inactividad — estado restaurado.",
                        node_id,
                        (now - last_ts).total_seconds(),
                    )
                    _already_flagged.discard(node_id)


async def _apply_status_update(node_id: str, status: str) -> None:
    """Llama a _update_status de forma segura (sync o async)."""
    if _update_status is None:
        logger.debug("_apply_status_update: sin actualizador de estado configurado.")
        return
    try:
        result = _update_status(node_id, status)
        # Si es una corutina, esperarla
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Error al actualizar estado del nodo '%s' a '%s': %s",
            node_id, status, exc,
        )


def get_flagged_nodes() -> list[str]:
    """Retorna la lista de nodos actualmente marcados como 'No Reporta'."""
    return list(_already_flagged)
