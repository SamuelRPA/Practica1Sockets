"""
server/network/socket_server.py
Servidor TCP asíncrono (asyncio) en el puerto 5000.

━━━ Protocolo de ENTRADA (Nodo → Servidor) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Formato JSON anidado (una línea terminada en \\n):
{
  "nodo":       "string",
  "ip_origen":  "192.168.x.x",
  "mac_origen": "AA:BB:CC:DD:EE:FF",
  "disco": {
    "nombre":    "string",    // ej: "/dev/sda" o "C:"
    "tipo":      "string",    // ej: "HDD" | "SSD" | "NVMe"
    "total_gb":  float,
    "usado_gb":  float,
    "libre_gb":  float,
    "iops":      int
  },
  "ram": {
    "total_gb":      float,
    "usado_gb":      float,
    "libre_gb":      float,
    "porcentaje_uso": float   // 0.0 – 100.0
  },
  "estado": "string"          // opcional, defecto "Activo"
}

━━━ Protocolo de SALIDA (Servidor → Nodo — Comandos) ━━━━━━━━━━━━━━━━━━━━━━
{
  "tipo":       "comando",
  "comando":    "RESCAN" | "REBOOT" | ...,
  "timestamp":  "ISO8601",
  "origen":     "admin@dashboard",
  "mensaje":    "string descriptivo",
  "id_mensaje": "uuid-string"
}
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from server.utils.logger import get_logger

logger = get_logger("SocketServer")

# ── Estado global ─────────────────────────────────────────────────────────────
# active_clients: { nodo -> asyncio.StreamWriter }
active_clients: dict[str, asyncio.StreamWriter] = {}

# last_seen: { nodo -> datetime (UTC) }
last_seen: dict[str, datetime] = {}

# Callback externo (inyectado por main.py)
_on_metrics_received = None   # callable(nodo, parsed_payload) -> Awaitable


def set_metrics_callback(callback) -> None:
    """Registra la función a llamar cuando se recibe un mensaje de métricas."""
    global _on_metrics_received
    _on_metrics_received = callback


# ── Gestión de clientes ────────────────────────────────────────────────────────

def _register_client(nodo: str, writer: asyncio.StreamWriter) -> None:
    if nodo not in active_clients:
        logger.info(
            "Nuevo nodo conectado: '%s' desde %s.",
            nodo, writer.get_extra_info("peername"),
        )
    active_clients[nodo] = writer
    last_seen[nodo] = datetime.utcnow()


def _unregister_client(nodo: Optional[str], writer: asyncio.StreamWriter) -> None:
    if nodo and active_clients.get(nodo) is writer:
        del active_clients[nodo]
        logger.warning("Nodo desconectado: '%s'.", nodo)


# ── Validación y extracción del JSON anidado ──────────────────────────────────

def _validate_and_extract(message: dict) -> Optional[dict]:
    """
    Valida el mensaje entrante y aplana los campos anidados de disco y ram.

    Returns:
        Diccionario plano listo para pasar a save_metrics(), o None si inválido.
    """
    # Campos raíz obligatorios
    for field in ("nodo", "ip_origen", "mac_origen", "disco", "ram"):
        if field not in message:
            logger.warning("Campo obligatorio faltante: '%s'.", field)
            return None

    disco = message["disco"]
    ram = message["ram"]

    # Campos de disco obligatorios
    for f in ("nombre", "tipo", "total_gb", "usado_gb", "libre_gb", "iops"):
        if f not in disco:
            logger.warning("Campo disco.'%s' faltante.", f)
            return None

    # Campos de RAM obligatorios (acepta tanto "porcentaje_uso" como "porcentaje")
    for f in ("total_gb", "usado_gb", "libre_gb"):
        if f not in ram:
            logger.warning("Campo ram.'%s' faltante.", f)
            return None
    if "porcentaje_uso" not in ram and "porcentaje" not in ram:
        logger.warning("Campo ram.'porcentaje_uso' (o 'porcentaje') faltante.")
        return None

    # Soportar ambas variantes del campo de porcentaje RAM
    ram_pct = ram.get("porcentaje_uso", ram.get("porcentaje", 0.0))

    return {
        "nodo":          str(message["nodo"]),
        "ip_origen":     str(message["ip_origen"]),
        "mac_origen":    str(message["mac_origen"]),
        "estado":        str(message.get("estado", "Activo")),
        # disco
        "disco_nombre":   str(disco["nombre"]),
        "disco_tipo":     str(disco["tipo"]),
        "disco_total_gb": float(disco["total_gb"]),
        "disco_usado_gb": float(disco["usado_gb"]),
        "disco_libre_gb": float(disco["libre_gb"]),
        "disco_iops":     int(disco["iops"]),
        # ram
        "ram_total_gb":   float(ram["total_gb"]),
        "ram_usado_gb":   float(ram["usado_gb"]),
        "ram_libre_gb":   float(ram["libre_gb"]),
        "ram_porcentaje": float(ram_pct),
    }


# ── Handler principal de cada conexión ────────────────────────────────────────

async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    nodo: Optional[str] = None
    peer = writer.get_extra_info("peername", ("?", "?"))
    logger.info("Conexión entrante desde %s:%s.", peer[0], peer[1])

    try:
        while True:
            # Leer hasta '\n' — funciona aunque el cliente no cierre la conexión
            try:
                raw_line = await reader.readline()
            except asyncio.IncompleteReadError as e:
                raw_line = e.partial

            if not raw_line:
                break  # El cliente cerró la conexión

            line = raw_line.decode("utf-8").strip()
            if not line:
                continue

            # ── Decodificación JSON ──────────────────────────────────────────
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "Mensaje malformado desde %s:%s — ignorado. Raw: %r",
                    peer[0], peer[1], line[:120],
                )
                continue

            # ── Validación y extracción de campos ────────────────────────────
            payload = _validate_and_extract(message)
            if payload is None:
                logger.warning(
                    "Mensaje con estructura inválida desde %s:%s — ignorado.",
                    peer[0], peer[1],
                )
                continue

            nodo = payload["nodo"]
            _register_client(nodo, writer)

            logger.info(
                "Métricas recibidas | nodo='%s' | ip=%s | "
                "disco_libre=%.2fGB | ram=%.1f%%",
                nodo, payload["ip_origen"],
                payload["disco_libre_gb"], payload["ram_porcentaje"],
            )

            # ── Callback hacia servicios (consolidator / db) ─────────────────
            if _on_metrics_received:
                try:
                    await _on_metrics_received(nodo, payload)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error en callback on_metrics_received: %s", exc)

            # ── ACK al nodo ──────────────────────────────────────────────────
            ack = json.dumps({
                "status": "OK",
                "nodo": nodo,
                "ts": datetime.utcnow().isoformat(),
            })
            writer.write((ack + "\n").encode("utf-8"))
            await writer.drain()

    except ConnectionResetError:
        logger.warning("Conexión reiniciada por el nodo '%s'.", nodo)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error inesperado en handler (nodo='%s'): %s", nodo, exc)
    finally:
        _unregister_client(nodo, writer)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ── Envío de comandos ─────────────────────────────────────────────────────────

async def send_command(
    nodo: str,
    comando: str,
    mensaje: str = "",
    origen: str = "admin@dashboard",
) -> bool:
    """
    Envía un comando al nodo usando el formato JSON de salida acordado.

    Args:
        nodo:    Identificador del nodo destino.
        comando: Nombre del comando (ej: 'RESCAN', 'REBOOT').
        mensaje: Descripción libre del comando (opcional).
        origen:  Identificador del emisor (defecto 'admin@dashboard').

    Returns:
        True si el envío fue exitoso, False si el nodo no está conectado.

    Formato JSON enviado:
    {
      "tipo":       "comando",
      "comando":    "<COMANDO>",
      "timestamp":  "ISO8601",
      "origen":     "admin@dashboard",
      "mensaje":    "<descripción>",
      "id_mensaje": "<uuid4>"
    }
    """
    writer = active_clients.get(nodo)
    if writer is None:
        logger.warning(
            "Comando '%s' fallido: nodo '%s' no está conectado.", comando, nodo
        )
        return False

    payload = json.dumps({
        "tipo":       "comando",
        "comando":    comando,
        "timestamp":  datetime.utcnow().isoformat(),
        "origen":     origen,
        "mensaje":    mensaje or f"Ejecutar {comando} en {nodo}",
        "id_mensaje": str(uuid.uuid4()),
    })

    try:
        writer.write((payload + "\n").encode("utf-8"))
        await writer.drain()
        logger.info(
            "Comando '%s' enviado a nodo '%s' (origen=%s).", comando, nodo, origen
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Error al enviar comando '%s' a nodo '%s': %s", comando, nodo, exc
        )
        _unregister_client(nodo, writer)
        return False


# ── Arranque del servidor ──────────────────────────────────────────────────────

async def start_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Inicia el servidor TCP y escucha indefinidamente."""
    server = await asyncio.start_server(
        client_connected_cb=_handle_client,
        host=host,
        port=port,
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info("Servidor CNS escuchando en %s (puerto %d).", addrs, port)

    async with server:
        await server.serve_forever()
