"""
server/services/failure_monitor.py
Tarea de fondo que detecta nodos inactivos.

Lógica:
  - Cada MONITOR_INTERVAL segundos revisa todos los nodos conocidos.
  - Si un nodo no ha reportado en más de NODE_TIMEOUT segundos, se marca
    como 'No Reporta' en la DB y se emite una alerta de log.
  - También elimina el nodo de active_nodes para que el frontend lo refleje inmediatamente.
  - Si el nodo vuelve a reportar, su estado se restaura a 'Activo'
    (gestionado por metrics_consolidator / db_manager.save_metrics).
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from server.utils.logger import get_logger

logger = get_logger("FailureMonitor")

# ── Parámetros configurables ──────────────────────────────────────────────────
MONITOR_INTERVAL: float = 5.0    # segundos entre cada revisión
NODE_TIMEOUT: float = 35.0       # segundos sin reporte → 'No Reporta'
OFFLINE_LOG_INTERVAL: float = 15.0  # segundos entre cada escritura del log de offline

# ── Callbacks externos (inyectados por main.py) ───────────────────────────────────
_get_last_seen = None     # callable() → dict[node_id, datetime]
_update_status = None     # callable(node_id, status) → bool  (puede ser sync)

# Referencia al dict active_nodes de socket_server (inyectada por main.py)
_get_active_nodes = None  # callable() → dict[node_id, dict]

# ── Estado interno ─────────────────────────────────────────────────────────────────────────
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


def set_active_nodes_source(fn) -> None:
    """Inyecta la función que devuelve el dict active_nodes de socket_server."""
    global _get_active_nodes
    _get_active_nodes = fn


# ── Tarea principal ────────────────────────────────────────────────────────────

async def monitor_loop() -> None:
    """
    Corutina principal del monitor de fallos.
    Debe ejecutarse como tarea asyncio independiente.

    Flujo por iteración:
      1. Obtiene last_seen de socket_server.
      2. Calcula nodos que superaron NODE_TIMEOUT.
      3. Marca nodos como 'No Reporta' en DB (evitando duplicar alertas).
      4. Elimina nodos de active_nodes para reflejar estado inmediatamente.
      5. Elimina de _already_flagged los nodos que volvieron a reportar.

    Lanza como subtarea paralela: offline_nodes_logger (cada 15 s).
    """
    logger.info(
        "Monitor de fallos iniciado (intervalo=%.1fs, timeout=%.1fs).",
        MONITOR_INTERVAL,
        NODE_TIMEOUT,
    )

    # Subtarea: log de nodos caídos cada OFFLINE_LOG_INTERVAL segundos
    asyncio.create_task(offline_nodes_logger(), name="OfflineNodesLogger")

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
                    # 🔥 Actualizar en BD y eliminar de active_nodes
                    await _apply_status_update_and_cleanup(node_id, "No Reporta")
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


async def _apply_status_update_and_cleanup(node_id: str, status: str) -> None:
    """
    Actualiza el estado en BD y elimina el nodo de active_nodes.
    """
    # 1. Actualizar en BD
    if _update_status is not None:
        try:
            result = _update_status(node_id, status)
            if asyncio.iscoroutine(result):
                await result
            logger.info(f"✅ Estado en BD actualizado: {node_id} -> {status}")
        except Exception as exc:
            logger.error(f"Error actualizando estado en BD para {node_id}: {exc}")
    
    # 2. 🔥 FORZAR ELIMINACIÓN DE active_nodes
    try:
        # Importar socket_server directamente para acceder a active_nodes
        from server.network import socket_server as net
        
        if node_id in net.active_nodes:
            logger.info(f"🗑️ Eliminando {node_id} de active_nodes por inactividad")
            del net.active_nodes[node_id]
        if node_id in net.active_clients:
            del net.active_clients[node_id]
    except Exception as exc:
        logger.error(f"Error eliminando {node_id} de active_nodes: {exc}")


def get_flagged_nodes() -> list[str]:
    """Retorna la lista de nodos actualmente marcados como 'No Reporta'."""
    return list(_already_flagged)


# ── Tarea: Log de nodos caídos (Modificación 2: Defensa) ──────────────────────

# Directorio de logs relativo al directorio de trabajo (raíz del proyecto)
_LOG_DIR = Path("logs")
_OFFLINE_LOG_FILE = _LOG_DIR / "offline_nodes.log"


async def offline_nodes_logger() -> None:
    """
    Subtarea que se ejecuta cada OFFLINE_LOG_INTERVAL (15) segundos.
    Revisa _already_flagged y active_nodes para escribir logs/offline_nodes.log
    con la lista de nodos en estado 'No Reporta', su IP y el tiempo sin reportar.
    Si no hay nodos caídos, escribe un mensaje de cluster operativo.
    """
    logger.info(
        "OfflineNodesLogger iniciado (intervalo=%.1fs).", OFFLINE_LOG_INTERVAL
    )
    while True:
        await asyncio.sleep(OFFLINE_LOG_INTERVAL)
        try:
            _write_offline_log()
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al escribir offline_nodes.log: %s", exc)


def _write_offline_log() -> None:
    """
    Escribe (o sobreescribe) logs/offline_nodes.log de forma síncrona.
    Se llama desde offline_nodes_logger dentro del event loop.
    """
    # Asegurar que el directorio existe
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()
    flagged = list(_already_flagged)

    if not flagged:
        content = "Estado del Cluster: Todos los nodos operativos\n"
    else:
        lines = [
            f"[{now.isoformat()} UTC] Nodos sin reporte ({len(flagged)}):",
            "-" * 60,
        ]
        # Obtener info extra de active_nodes si está disponible
        active_nodes_map: dict = {}
        if _get_active_nodes is not None:
            try:
                active_nodes_map = _get_active_nodes()
            except Exception:  # noqa: BLE001
                active_nodes_map = {}

        last_seen_map: dict = {}
        if _get_last_seen is not None:
            try:
                last_seen_map = _get_last_seen()
            except Exception:  # noqa: BLE001
                last_seen_map = {}

        for node_id in sorted(flagged):
            node_data = active_nodes_map.get(node_id, {})
            ip = node_data.get("ip_origen", "desconocida")
            last_ts = last_seen_map.get(node_id)
            if last_ts:
                elapsed = (now - last_ts).total_seconds()
                elapsed_str = f"{elapsed:.1f}s sin reportar"
            else:
                elapsed_str = "tiempo desconocido"
            lines.append(f"  - {node_id:<20} IP: {ip:<18} {elapsed_str}")

        content = "\n".join(lines) + "\n"

    with open(_OFFLINE_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(
        "offline_nodes.log actualizado: %d nodo(s) offline.", len(flagged)
    )