"""
server/network/socket_server.py
Servidor TCP asíncrono (asyncio) en el puerto 5000.

━━━ Protocolo de ENTRADA (Nodo → Servidor) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Formato JSON anidado (una línea terminada en \\n):
{
  "nodo":            "string",   // DEBE ser minúsculas sin espacios (ej: 'oruro', 'lapaz')
  "ip_origen":       "192.168.x.x",        // opcional
  "mac_origen":      "AA:BB:CC:DD:EE:FF",  // opcional
  "display_name":    "string",   // opcional; nombre legible (ej: 'Oruro Regional')
  "uptime_seconds":  int,        // opcional; defecto 0
  "disco": {
    "nombre":    "string",    // ej: "/dev/sda" o "C:"
    "tipo":      "string",    // ej: "HDD" | "SSD" | "NVMe"
    "total_gb":  float,
    "usado_gb":  float,       // también acepta "used_gb"
    "libre_gb":  float,       // también acepta "free_gb"
    "iops":      int
  },
  "ram": {
    "total_gb":      float,
    "usado_gb":      float,       // también acepta "used_gb"
    "libre_gb":      float,       // también acepta "free_gb"
    "porcentaje_uso": float        // 0.0 – 100.0
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


# ── Extracción del JSON anidado ───────────────────────────────────────────────

def _validate_and_extract(message: dict) -> Optional[dict]:
    """
    Extrae y normaliza los campos del mensaje entrante.

    Usa .get() con valores por defecto en TODOS los campos para que NUNCA
    se rechace un mensaje ni se lance un KeyError.

    Acepta variantes de campo:
      - disco: "usado_gb" o "used_gb", "libre_gb" o "free_gb"
      - uptime_seconds: nivel raíz o dentro de "ram"

    Retorna None únicamente si el campo "nodo" está ausente por completo.
    """
    if "nodo" not in message:
        logger.warning("Mensaje sin campo 'nodo' — ignorado.")
        return None

    disco = message.get("disco") or {}
    ram   = message.get("ram")   or {}

    identifier = str(message["nodo"]).lower().strip()

    # Disco: acepta usado_gb o used_gb; libre_gb o free_gb
    total_gb = float(disco.get("total_gb", 0.0))
    used_gb  = float(disco.get("usado_gb", disco.get("used_gb", 0.0)))
    free_gb  = float(disco.get("libre_gb", disco.get("free_gb", total_gb - used_gb)))

    # RAM: solo necesitamos total_gb
    ram_gb = float(ram.get("total_gb", 0.0))

    # uptime_seconds: raíz del mensaje o dentro de ram
    uptime_seconds = int(
        message.get("uptime_seconds", ram.get("uptime_seconds", 0))
    )

    return {
        # Claves del SP sp_InsertMetricAndUpdateNode
        "identifier":     identifier,
        "display_name":   str(message.get("display_name", identifier)),
        "total_gb":       total_gb,
        "used_gb":        used_gb,
        "free_gb":        free_gb,
        "iops":           int(disco.get("iops", 0)),
        "disk_name":      str(disco.get("nombre", disco.get("name", "unknown"))),
        "disk_type":      str(disco.get("tipo",   disco.get("type",  "HDD"))),
        "ram_gb":         ram_gb,
        "uptime_seconds": uptime_seconds,
        # Campos extra para logging / memoria interna
        "ip_origen":      str(message.get("ip_origen",  "")),
        "mac_origen":     str(message.get("mac_origen", "")),
        "estado":         str(message.get("estado", "Activo")),
        "free_gb_disco":  free_gb,
        "used_gb_disco":  used_gb,
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
                    "Mensaje malformado desde %s:%s — ignorado.",
                    peer[0], peer[1],
                )
                continue

            # ── Extracción con tolerancia a variantes de campo ───────────────
            payload = _validate_and_extract(message)
            if payload is None:
                logger.warning(
                    "Mensaje sin campo 'nodo' desde %s:%s — ignorado.",
                    peer[0], peer[1],
                )
                continue

            nodo = payload["identifier"]
            _register_client(nodo, writer)

            logger.info(
                "Métricas recibidas | identifier='%s' | ip=%s | free_gb=%.2f | ram_gb=%.2f",
                nodo,
                payload.get("ip_origen", "?"),
                payload.get("free_gb", 0.0),
                payload.get("ram_gb", 0.0),
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

    Returns:
        True si el envío fue exitoso, False si el nodo no está conectado.
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
