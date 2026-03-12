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

    buf_str = ""
    decoder = json.JSONDecoder()

    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk and not buf_str:
                break
                
            if chunk:
                buf_str += chunk.decode("utf-8", errors="replace")

            while buf_str:
                buf_str = buf_str.lstrip()
                if not buf_str:
                    break
                    
                start_idx = buf_str.find('{')
                if start_idx == -1:
                    bad_msg = buf_str.strip()
                    if bad_msg:
                        print(f"[WARN] Se recibió un mensaje que no es JSON técnico: {bad_msg}")
                        logger.warning("Mensaje malformado desde %s:%s — ignorado.", peer[0], peer[1])
                        writer.write("SERVIDOR_CNS: Mensaje recibido pero no es una métrica válida\n".encode("utf-8"))
                        await writer.drain()
                    buf_str = ""
                    break

                if start_idx > 0:
                    bad_msg = buf_str[:start_idx].strip()
                    if bad_msg:
                        print(f"[WARN] Se recibió un mensaje que no es JSON técnico: {bad_msg}")
                        logger.warning("Mensaje con basura inicial desde %s:%s — limpiando.", peer[0], peer[1])
                        writer.write("SERVIDOR_CNS: Mensaje recibido pero no es una métrica válida\n".encode("utf-8"))
                        await writer.drain()
                    buf_str = buf_str[start_idx:]
                
                try:
                    data, end_idx = decoder.raw_decode(buf_str)
                    raw_str = buf_str[:end_idx]
                    buf_str = buf_str[end_idx:]
                except json.JSONDecodeError:
                    if len(buf_str) > 512 * 1024:
                        logger.warning("Buffer overflow (malformed JSON) from %s:%s. Limpiando.", peer[0], peer[1])
                        buf_str = ""
                    # Not enough data for a complete JSON yet
                    break
                
                print(f"[RAW RECEIVE] Contenido recibido: {raw_str}")

                logger.info(
                    "DEBUG: Datos recibidos del cliente: llaves_raíz=%s | disco=%s",
                    list(data.keys()) if isinstance(data, dict) else [],
                    list((data.get("disco") or {}).keys()) if isinstance(data, dict) else [],
                )

                # ── Validación de ser una métrica válida ──────────────────────────
                if not isinstance(data, dict) or "nodo" not in data:
                    logger.warning(
                        "Mensaje sin campo 'nodo' desde %s:%s — ignorado.",
                        peer[0], peer[1],
                    )
                    writer.write("SERVIDOR_CNS: Mensaje recibido pero no es una métrica válida\n".encode("utf-8"))
                    await writer.drain()
                    continue

                nodo_raw = data["nodo"]
                print(f"[SUCCESS] Paquete completo recibido de {nodo_raw}.")

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
                            writer.write(b"ERROR: TIME_MISMATCH\n")
                            await writer.drain()
                            # MOD 1: No bloquear el guardado en RAM si la diferencia es mayor a 60s, simplemente informamos de error
                            # continue  <- (removido para no bloquear registro en active_nodes)
                    except (ValueError, TypeError):
                        logger.debug("Campo 'timestamp' no es numérico, ignorando validación.")
                else:
                    print(f"[INFO] Cliente {peer[0]} no envió timestamp. Se ignora validación y se guardan datos en STATUS por ahora.")

                # ── Respuesta inmediata al cliente (antes de procesar DB) ─────────
                writer.write(b"OK\n")
                await writer.drain()

                # ── Extracción anidada directa (Mapeo de Datos) ───────────────────
                nodo = str(nodo_raw).lower().strip()

                try:
                    total_gb = float(data['disco']['total_gb'])
                except (KeyError, TypeError, ValueError):
                    total_gb = float(data.get("disco", {}).get("total_gb", 0.0))

                try:
                    used_gb = float(data['disco']['used_gb'])
                except (KeyError, TypeError, ValueError):
                    used_gb = float(data.get("disco", {}).get("used_gb", data.get("disco", {}).get("usado_gb", 0.0)))

                try:
                    free_gb = float(data['disco']['free_gb'])
                except (KeyError, TypeError, ValueError):
                    free_gb = float(data.get("disco", {}).get("free_gb", data.get("disco", {}).get("libre_gb", total_gb - used_gb if total_gb and used_gb else 0.0)))

                try:
                    iops = int(data['disco']['iops'])
                except (KeyError, TypeError, ValueError):
                    iops = int(data.get("disco", {}).get("iops", 0))

                try:
                    disk_name = str(data['disco']['nombre'])
                except (KeyError, TypeError, ValueError):
                    disk_name = str(data.get("disco", {}).get("nombre", data.get("disco", {}).get("name", "unknown")))

                try:
                    disk_type = str(data['disco']['tipo'])
                except (KeyError, TypeError, ValueError):
                    disk_type = str(data.get("disco", {}).get("tipo", data.get("disco", {}).get("type", "HDD")))

                try:
                    ram_gb = float(data['ram']['total_gb'])
                except (KeyError, TypeError, ValueError):
                    ram_gb = float(data.get("ram", {}).get("total_gb", 0.0))

                try:
                    uptime_seconds = int(data['uptime_seconds'])
                except (KeyError, TypeError, ValueError):
                    uptime_seconds = int(data.get("uptime_seconds", data.get("ram", {}).get("uptime_seconds", 0)))

                display_name = str(data.get("display_name", nodo))

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
                    "disco":          data.get("disco", {}),
                    "ram":            data.get("ram", {}),
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
