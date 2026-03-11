"""
main.py
Punto de entrada del CNS Server (Central Monitoring Server).

Orquesta:
  1. Sistema de logging
  2. Conexión a MySQL (DBManager)
  3. Inyección de dependencias entre módulos
  4. Tarea de fondo: monitor de fallos
  5. Servidor TCP asíncrono (puerto 5000)
  6. Consola de comandos interactiva (en hilo separado)
"""

import asyncio
import threading
from datetime import datetime

from server.utils.logger import setup_logger, get_logger
from server.database.db_manager import DBManager
from server.network import socket_server as net
from server.services import metrics_consolidator as consolidator
from server.services import failure_monitor as monitor

# ── Inicializar logging PRIMERO ────────────────────────────────────────────────
setup_logger()
logger = get_logger("Main")

# ── Instanciar DB Manager ──────────────────────────────────────────────────────
db = DBManager()


# ══════════════════════════════════════════════════════════════════════════════
# Consola de comandos (hilo separado, no bloqueante)
# ══════════════════════════════════════════════════════════════════════════════

AVAILABLE_COMMANDS = ["RESCAN", "REBOOT", "STATUS", "LIST", "HELP", "EXIT"]


def _print_help() -> None:
    """Muestra los comandos disponibles en la consola."""
    print(
        "\n╔══════════════════════════════════════════╗"
        "\n║        CNS Server — Consola Operator     ║"
        "\n╠══════════════════════════════════════════╣"
        "\n║  LIST              → Listar nodos activos║"
        "\n║  STATUS            → Totales del cluster ║"
        "\n║  RESCAN  <node_id> → Enviar RESCAN        ║"
        "\n║  REBOOT  <node_id> → Enviar REBOOT        ║"
        "\n║  HELP              → Mostrar esta ayuda   ║"
        "\n║  EXIT              → Detener el servidor  ║"
        "\n╚══════════════════════════════════════════╝\n"
    )


def _console_worker(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    """
    Hilo síncrono que lee comandos del operador por stdin.
    Despacha acciones al event loop principal mediante call_coroutine_threadsafe.
    """
    _print_help()
    while True:
        try:
            raw = input("CNS> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].upper()
        args = parts[1:]

        # ── LIST ──────────────────────────────────────────────────────────────
        if cmd == "LIST":
            nodes = list(net.active_clients.keys())
            if nodes:
                print(f"  Nodos activos ({len(nodes)}): {', '.join(nodes)}")
            else:
                print("  Sin nodos conectados actualmente.")
            logger.info("Consola: LIST → %d nodo(s) activos.", len(nodes))

        # ── STATUS ────────────────────────────────────────────────────────────
        elif cmd == "STATUS":
            flagged = monitor.get_flagged_nodes()
            totals = consolidator.get_cluster_totals(exclude=set(flagged))
            all_nodes = list(net.active_nodes.keys())
            reporting = [n for n in all_nodes if n not in flagged]
            print(
                f"\n  Cluster Summary (datos en memoria — sin DB)\n"
                f"  ├─ Nodos reportando : {len(reporting)} → {reporting if reporting else 'ninguno'}\n"
                f"  ├─ Capacity Total   : {totals['capacity_total']:.2f} GB\n"
                f"  ├─ Used Total       : {totals['used_total']:.2f} GB\n"
                f"  ├─ Free Total       : {totals['free_total']:.2f} GB\n"
                f"  └─ Sin reporte      : {flagged if flagged else 'ninguno'}\n"
            )
            logger.info("Consola: STATUS consultado.")

        # ── RESCAN / REBOOT ───────────────────────────────────────────────────
        elif cmd in ("RESCAN", "REBOOT"):
            if not args:
                print(f"  Uso: {cmd} <nodo>")
                continue
            nodo_id = args[0]
            mensaje = " ".join(args[1:]) if len(args) > 1 else f"Operador solicitó {cmd}"
            future = asyncio.run_coroutine_threadsafe(
                net.send_command(nodo_id, cmd, mensaje=mensaje), loop
            )
            success = future.result(timeout=5.0)
            if success:
                print(f"  ✔ Comando '{cmd}' enviado a '{nodo_id}'. Esperando ACK...")
                logger.info("Consola: comando '%s' enviado a '%s'.", cmd, nodo_id)
            else:
                print(f"  ✘ No se pudo enviar '{cmd}' a '{nodo_id}' (nodo no conectado o error).")

        # ── HELP ──────────────────────────────────────────────────────────────
        elif cmd == "HELP":
            _print_help()

        # ── EXIT ──────────────────────────────────────────────────────────────
        elif cmd == "EXIT":
            logger.info("Consola: solicitud de apagado recibida.")
            print("  Deteniendo el servidor CNS...")
            asyncio.run_coroutine_threadsafe(
                _set_stop(stop_event), loop
            )
            break

        else:
            print(f"  Comando desconocido: '{cmd}'. Escribe HELP para ver opciones.")


async def _set_stop(event: asyncio.Event) -> None:
    event.set()


# ══════════════════════════════════════════════════════════════════════════════
# Inyección de dependencias y bootstrap
# ══════════════════════════════════════════════════════════════════════════════

def _wire_dependencies() -> None:
    """
    Conecta los módulos entre sí mediante callbacks (patrón Dependency Injection).
    De esta forma, los módulos no se importan circularmente.
    """
    # ── socket_server → metrics_consolidator ─────────────────────────────────
    net.set_metrics_callback(consolidator.on_metrics_received)

    # ── metrics_consolidator → db_manager ────────────────────────────────────
    consolidator.set_db_callback(db.save_metrics)

    # ── failure_monitor → socket_server (last_seen) ──────────────────────────
    monitor.set_last_seen_source(lambda: dict(net.last_seen))

    # ── failure_monitor → socket_server (active_nodes para log offline) ──────
    monitor.set_active_nodes_source(lambda: dict(net.active_nodes))

    # ── failure_monitor → db_manager (actualizar estado) ───────────────────
    monitor.set_status_updater(db.update_node_status)

    logger.info("Dependencias inyectadas correctamente.")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    logger.info("═" * 60)
    logger.info("  CNS Server — Central Node Server arrancando...")
    logger.info("  Hora UTC: %s", datetime.utcnow().isoformat())
    logger.info("═" * 60)

    _wire_dependencies()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # ── Tarea de fondo: monitor de fallos ─────────────────────────────────────
    monitor_task = asyncio.create_task(
        monitor.monitor_loop(),
        name="FailureMonitor",
    )

    # ── Hilo de consola (no bloquea el event loop) ────────────────────────────
    console_thread = threading.Thread(
        target=_console_worker,
        args=(loop, stop_event),
        daemon=True,
        name="ConsoleThread",
    )
    console_thread.start()
    logger.info("Consola de comandos iniciada (hilo separado).")

    # ── Servidor TCP ──────────────────────────────────────────────────────────
    server_task = asyncio.create_task(
        net.start_server(host="0.0.0.0", port=5000),
        name="SocketServer",
    )

    # Esperar hasta que la consola ordene el apagado o se interrumpa con Ctrl+C
    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Iniciando apagado controlado del servidor...")
        monitor_task.cancel()
        server_task.cancel()
        await asyncio.gather(monitor_task, server_task, return_exceptions=True)
        logger.info("Servidor CNS detenido. Hasta luego.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [CNS] Interrupción por teclado (Ctrl+C). Cerrando...")
