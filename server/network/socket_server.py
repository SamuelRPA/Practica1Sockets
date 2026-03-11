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
import time
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

    Mapeo inteligente de claves:
      - disco.used_gb  (preferido) o disco.usado_gb  (alias español)
      - disco.free_gb  (preferido) o disco.libre_gb  (alias español)
      - uptime_seconds: nivel raíz o dentro de "ram"

    Retorna None únicamente si el campo "nodo" está ausente por completo.
    """
    if "nodo" not in message:
        logger.warning("Mensaje sin campo 'nodo' — ignorado.")
        return None

    # Extraer sub-objetos con fallback a dict vacío
    disco = message.get("disco", {}) or {}
    ram   = message.get("ram",   {}) or {}

    identifier = str(message["nodo"]).lower().strip()

    # Extraer con valores por defecto para que nunca dé 0 por error de llave
    total_gb = float(disco.get("total_gb", 0.0) or 0.0)

    # Prioridad: clave inglesa (used_gb) → alias español (usado_gb) → 0.0
    used_gb  = float(disco.get("used_gb",  disco.get("usado_gb",  0.0)) or 0.0)
    free_gb  = float(disco.get("free_gb",  disco.get("libre_gb",  total_gb - used_gb)) or 0.0)
    iops     = int(disco.get("iops", 0) or 0)

    ram_gb = float(ram.get("total_gb", 0.0) or 0.0)

    # uptime_seconds: nivel raíz del mensaje o dentro de ram
    uptime_seconds = int(
        message.get("uptime_seconds", ram.get("uptime_seconds", 0)) or 0
    )

    return {
        # Claves del SP sp_InsertMetricAndUpdateNode
        "identifier":     identifier,
        "display_name":   str(message.get("display_name", identifier)),
        "total_gb":       total_gb,
        "used_gb":        used_gb,
        "free_gb":        free_gb,
        "iops":           iops,
        "disk_name":      str(disco.get("nombre", disco.get("name", "unknown"))),
        "disk_type":      str(disco.get("tipo",   disco.get("type",  "HDD"))),
        "ram_gb":         ram_gb,
        "uptime_seconds": uptime_seconds,
        # Campos extra para logging / memoria interna
        "ip_origen":      str(message.get("ip_origen",  "")),
        "mac_origen":     str(message.get("mac_origen", "")),
        "estado":         str(message.get("estado", "Activo")),
    }


# ── Estado en memoria (nodos activos) ────────────────────────────────────────
# active_nodes se actualiza CON PRIORIDAD RAM: siempre antes de intentar DB.
# { identifier -> {payload + "ts": datetime} }
active_nodes: dict[str, dict] = {}


# ── Handler principal de cada conexión ────────────────────────────────────────

async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    nodo: Optional[str] = None
    peer = writer.get_extra_info("peername", ("?", "?"))
    logger.info("Conexión entrante desde %s:%s.", peer[0], peer[1])

    buf = b""   # buffer acumulador para mensajes sin \n al final

    try:
        while True:
            # Leer chunk (hasta \n o hasta 64KB si no hay \n)
            try:
                chunk = await reader.readuntil(b"\n")
            except asyncio.IncompleteReadError as e:
                # EOF: el cliente cerró la conexión sin enviar \n
                chunk = e.partial
            except asyncio.LimitOverrunError:
                chunk = await reader.read(65536)

            buf += chunk

            if not buf:
                break  # conexión cerrada, buffer vacío

            line = buf.decode("utf-8", errors="replace").strip()
            buf = b""   # limpiar buffer tras consumir

            if not line:
                continue

            # ── Decodificación JSON ──────────────────────────────────────────
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Mensaje malformado desde %s:%s — ignorado. (%s)",
                    peer[0], peer[1], exc,
                )
                if not chunk:   # no hay más datos que esperar
                    break
                continue

            logger.info(
                "DEBUG: Datos recibidos del cliente: llaves_raíz=%s | disco=%s",
                list(data.keys()),
                list((data.get("disco") or {}).keys()),
            )

            # ── Validación de timestamp (Modificación 1: Defensa) ───────────
            ts_value = data.get("timestamp")
            if ts_value is not None:
                try:
                    ts_float = float(ts_value)
                    time_diff = abs(time.time() - ts_float)
                    if time_diff > 60:
                        logger.warning(
                            "Desfase de tiempo detectado para nodo desde %s:%s — diff=%.1fs > 60s.",
                            peer[0], peer[1], time_diff,
                        )
                        writer.write(b"ERROR: CONFIG_REQUIRED_TIME_MISMATCH\n")
                        await writer.drain()
                        if not chunk:
                            break
                        continue
                except (ValueError, TypeError):
                    logger.debug("Campo 'timestamp' no es numérico, ignorando validación.")

            # ── Respuesta inmediata al cliente (antes de procesar DB) ─────────
            writer.write(b"OK\n")
            await writer.drain()

            # ── Extracción anidada con valores por defecto ────────────────────
            if "nodo" not in data:
                logger.warning(
                    "Mensaje sin campo 'nodo' desde %s:%s — ignorado.",
                    peer[0], peer[1],
                )
                if not chunk:
                    break
                continue

            nodo = str(data["nodo"]).lower().strip()

            total_gb       = data.get("disco", {}).get("total_gb",       0.0) or 0.0
            used_gb        = data.get("disco", {}).get("used_gb",         data.get("disco", {}).get("usado_gb", 0.0)) or 0.0
            free_gb        = data.get("disco", {}).get("free_gb",         data.get("disco", {}).get("libre_gb",  total_gb - used_gb)) or 0.0
            iops           = data.get("disco", {}).get("iops",            0) or 0
            disk_name      = data.get("disco", {}).get("nombre",          data.get("disco", {}).get("name", "unknown"))
            disk_type      = data.get("disco", {}).get("tipo",            data.get("disco", {}).get("type", "HDD"))
            ram_gb         = data.get("ram",   {}).get("total_gb",        0.0) or 0.0
            uptime_seconds = data.get("uptime_seconds", data.get("ram", {}).get("uptime_seconds", 0)) or 0
            display_name   = data.get("display_name", nodo)

            total_gb       = float(total_gb)
            used_gb        = float(used_gb)
            free_gb        = float(free_gb)
            iops           = int(iops)
            ram_gb         = float(ram_gb)
            uptime_seconds = int(uptime_seconds)
            display_name   = str(display_name)
            disk_name      = str(disk_name)
            disk_type      = str(disk_type)

            print(f"---> Recibido de '{nodo}': {total_gb} GB capacidad | {used_gb} GB usado | {free_gb} GB libre | RAM {ram_gb} GB")

            payload = {
                "identifier":     nodo,
                "display_name":   display_name,
                "total_gb":       total_gb,
                "used_gb":        used_gb,
                "free_gb":        free_gb,
                "iops":           iops,
                "disk_name":      disk_name,
                "disk_type":      disk_type,
                "ram_gb":         ram_gb,
                "uptime_seconds": uptime_seconds,
                "ip_origen":      str(data.get("ip_origen",  "")),
                "mac_origen":     str(data.get("mac_origen", "")),
                "estado":         str(data.get("estado", "Activo")),
            }

            # ── 1. GUARDAR EN MEMORIA (prioridad, siempre funciona) ───────────
            active_nodes[nodo] = {**payload, "ts": datetime.utcnow()}
            _register_client(nodo, writer)
            print(f"[DEBUG] Nodo '{nodo}' procesado correctamente.")
            logger.info("[DEBUG] Nodo '%s' procesado correctamente.", nodo)

            # ── 2. ENVIAR A RAILWAY (si falla, el nodo sigue en memoria) ─────
            if _on_metrics_received:
                try:
                    await _on_metrics_received(nodo, payload)
                    logger.info("✅ Datos de '%s' enviados a DB.", nodo)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "❌ Error al enviar datos de '%s' a DB: %s — nodo permanece en memoria.",
                        nodo, exc,
                    )

            if not chunk:
                break  # EOF alcanzado, no esperar más datos

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
