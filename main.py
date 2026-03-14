"""
main.py
Punto de entrada del CNS Server (Central Monitoring Server).
VERSIÓN CORREGIDA - USA EL ESTADO DE LA BD Y LIMPIA DATOS DE NODOS INACTIVOS
"""

import asyncio
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

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

# ── Variable global para el event loop de asyncio ─────────────────────────────
event_loop = None

# ── Crear API Flask para React ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ============================================
# FUNCIONES PARA MENSAJES
# ============================================

def guardar_mensaje_db(node_id, mensaje):
    """Guarda un mensaje en la tabla Messages"""
    logger.info(f"💾 Intentando guardar mensaje para node_id={node_id}: {mensaje[:50]}...")
    conn = db._get_connection()
    if conn is None:
        logger.error("❌ No se pudo conectar a DB para guardar mensaje")
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Messages (node_id, timestamp, message, ack_timestamp)
            VALUES (%s, NOW(), %s, NULL)
        """, (node_id, mensaje))
        conn.commit()
        mensaje_id = cursor.lastrowid
        logger.info(f"✅ Mensaje guardado en DB (id={mensaje_id})")
        cursor.close()
        conn.close()
        return mensaje_id
    except Exception as e:
        logger.error(f"❌ Error guardando mensaje: {e}")
        return None

def actualizar_ack_mensaje(mensaje_id):
    """Actualiza el ack_timestamp cuando el cliente confirma recepción"""
    conn = db._get_connection()
    if conn is None:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Messages 
            SET ack_timestamp = NOW() 
            WHERE id = %s
        """, (mensaje_id,))
        conn.commit()
        logger.info(f"✅ ACK registrado para mensaje {mensaje_id}")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error actualizando ACK: {e}")

def actualizar_ack_callback(mensaje_id):
    """Callback para cuando llega un ACK desde socket_server"""
    logger.info(f"📨 Callback ACK recibido para mensaje {mensaje_id}")
    actualizar_ack_mensaje(mensaje_id)

# ============================================
# ENDPOINTS API
# ============================================

@app.route('/api/nodos', methods=['GET'])
def get_nodos():
    try:
        # Usar el método del db_manager para obtener el resumen
        resumen = db.get_cluster_summary()
        nodos_bd = resumen.get('nodes', [])
        
        # Lista FIJA de los 9 nodos
        todos_los_nodos = [
            {"identifier": "lapaz", "display_name": "La Paz"},
            {"identifier": "cochabamba", "display_name": "Cochabamba"},
            {"identifier": "santacruz", "display_name": "Santa Cruz"},
            {"identifier": "oruro", "display_name": "Oruro"},
            {"identifier": "potosi", "display_name": "Potosí"},
            {"identifier": "chuquisaca", "display_name": "Chuquisaca"},
            {"identifier": "tarija", "display_name": "Tarija"},
            {"identifier": "beni", "display_name": "Beni"},
            {"identifier": "pando", "display_name": "Pando"}
        ]
        
        resultado = []
        
        for nodo_base in todos_los_nodos:
            # Buscar en los datos de la BD
            nodo_bd = next((n for n in nodos_bd if n["identifier"] == nodo_base["identifier"]), None)
            
            # USAR EL ESTADO DE LA BD (ya actualizado por failure_monitor)
            if nodo_bd:
                status = nodo_bd.get("status", "No Reporta")
                
                # 🔥 Si está inactivo, los datos deben ser 0
                if status == "Activo":
                    total_gb = float(nodo_bd.get("total_gb", 0))
                    used_gb = float(nodo_bd.get("used_gb", 0))
                    free_gb = float(nodo_bd.get("free_gb", 0))
                    iops = int(nodo_bd.get("iops", 0))
                    disk_type = nodo_bd.get("disk_type", "N/A")
                    ram_gb = float(nodo_bd.get("ram_gb", 0))
                    ip = nodo_bd.get("ip", "")
                    mac = nodo_bd.get("mac", "")
                    discos = nodo_bd.get("discos", [])
                else:
                    # Nodo inactivo: todos los datos a 0 o vacío
                    total_gb = 0
                    used_gb = 0
                    free_gb = 0
                    iops = 0
                    disk_type = "N/A"
                    ram_gb = 0
                    ip = ""
                    mac = ""
                    discos = []
                
                resultado.append({
                    "id": nodo_bd.get("id"),
                    "identifier": nodo_bd["identifier"],
                    "display_name": nodo_bd["display_name"],
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "iops": iops,
                    "disk_type": disk_type,
                    "ram_gb": ram_gb,
                    "ip": ip,
                    "mac": mac,
                    "status": status,
                    "last_seen": nodo_bd.get("last_seen"),
                    "discos": discos
                })
            else:
                # Nodo sin datos en BD
                resultado.append({
                    "identifier": nodo_base["identifier"],
                    "display_name": nodo_base["display_name"],
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "iops": 0,
                    "disk_type": "N/A",
                    "ram_gb": 0,
                    "ip": "",
                    "mac": "",
                    "status": "No Reporta",
                    "last_seen": None,
                    "discos": []
                })
        
        # Log para depuración
        activos = sum(1 for n in resultado if n["status"] == "Activo")
        logger.info(f"📊 Nodos enviados: {len(resultado)} total, {activos} activos (desde BD)")
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error en /api/nodos: {e}")
        return jsonify([])


@app.route('/api/cluster/resumen', methods=['GET'])
def get_resumen():
    try:
        # Obtener todos los nodos
        nodos_response = get_nodos().json
        activos = [n for n in nodos_response if n["status"] == "Activo"]
        
        # Calcular totales solo de activos
        total_capacidad = sum(n.get("total_gb", 0) for n in activos)
        total_usado = sum(n.get("used_gb", 0) for n in activos)
        total_libre = sum(n.get("free_gb", 0) for n in activos)
        
        return jsonify({
            'total_capacidad_tb': total_capacidad / 1000,
            'total_usado_tb': total_usado / 1000,
            'total_libre_tb': total_libre / 1000,
            'nodos_activos': len(activos),
            'total_nodos': 9,
            'porcentaje_uso_global': (total_usado / total_capacidad * 100) if total_capacidad > 0 else 0,
            'mensaje': f"Reportaron {len(activos)} de 9"
        })
    except Exception as e:
        logger.error(f"Error en /api/cluster/resumen: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/nodos/<nodo_id>/historial', methods=['GET'])
def get_historial_nodo(nodo_id):
    """Retorna historial de métricas de un nodo específico"""
    try:
        conn = db._get_connection()
        if conn is None:
            return jsonify({"error": "No hay conexión a DB"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                m.timestamp,
                m.used_space_gb as used_gb,
                m.total_capacity_gb as total_gb,
                m.free_space_gb as free_gb
            FROM Metrics m
            INNER JOIN Nodes n ON m.node_id = n.id
            WHERE n.identifier = %s
            ORDER BY m.timestamp DESC
            LIMIT 30
        """, (nodo_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Formatear fechas
        for row in rows:
            if row["timestamp"]:
                row["timestamp"] = row["timestamp"].isoformat()
        
        logger.info(f"Historial para {nodo_id}: {len(rows)} registros")
        return jsonify(rows)
        
    except Exception as e:
        logger.error(f"Error en historial de {nodo_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/mensajes/<nodo_id>', methods=['POST'])
def enviar_mensaje(nodo_id):
    """Envía un comando a un nodo específico y lo guarda en DB"""
    global event_loop
    
    try:
        data = request.json
        comando = data.get('comando', 'MENSAJE')
        mensaje_texto = data.get('mensaje', f'Comando {comando}')
        
        logger.info(f"📨 Recibido comando '{comando}' para nodo '{nodo_id}'")
        
        # 1. Obtener node_id desde la base de datos
        conn = db._get_connection()
        if not conn:
            logger.error("❌ No hay conexión a DB")
            return jsonify({"status": "error", "mensaje": "Error de conexión a DB"}), 500
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM Nodes WHERE identifier = %s", (nodo_id,))
            node = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not node:
                logger.error(f"❌ Nodo '{nodo_id}' no existe en BD")
                return jsonify({
                    "status": "error", 
                    "mensaje": f"Nodo '{nodo_id}' no existe en BD"
                }), 404
            
            node_id_db = node["id"]
            logger.info(f"✅ Node ID encontrado: {node_id_db} para '{nodo_id}'")
            
            # 2. Guardar mensaje en DB (pendiente de ACK)
            mensaje_completo = f"{comando}: {mensaje_texto}"
            mensaje_id = guardar_mensaje_db(node_id_db, mensaje_completo)
            
            if not mensaje_id:
                logger.error("❌ No se pudo guardar mensaje en BD")
                return jsonify({"status": "error", "mensaje": "Error guardando en BD"}), 500
            
            logger.info(f"✅ Mensaje guardado con ID: {mensaje_id}")
            
        except Exception as e:
            logger.error(f"❌ Error en operación de BD: {e}")
            return jsonify({"status": "error", "mensaje": str(e)}), 500
        
        # 3. Verificar si el nodo está conectado (para enviar por socket)
        if nodo_id not in net.active_nodes:
            logger.warning(f"⚠️ Nodo '{nodo_id}' no está conectado")
            return jsonify({
                "status": "error", 
                "mensaje": f"Nodo '{nodo_id}' no está conectado"
            }), 404
        
        # 4. Enviar comando usando el socket_server con el loop guardado
        try:
            if event_loop is None:
                logger.error("❌ Event loop no disponible")
                return jsonify({"status": "error", "mensaje": "Error interno del servidor"}), 500
                
            future = asyncio.run_coroutine_threadsafe(
                net.send_command(nodo_id, comando, mensaje=mensaje_texto, mensaje_id=mensaje_id),
                event_loop
            )
            success = future.result(timeout=5.0)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout enviando comando a '{nodo_id}'")
            return jsonify({"status": "error", "mensaje": "Timeout al enviar comando"}), 500
        except Exception as e:
            logger.error(f"❌ Error enviando comando por socket: {e}")
            return jsonify({"status": "error", "mensaje": str(e)}), 500
        
        if success:
            logger.info(f"✅ Comando '{comando}' enviado a '{nodo_id}' (msg_id={mensaje_id})")
            return jsonify({
                "status": "enviado", 
                "nodo": nodo_id, 
                "comando": comando,
                "mensaje_id": mensaje_id,
                "mensaje": f"Comando {comando} enviado correctamente"
            })
        else:
            logger.error(f"❌ No se pudo enviar comando a '{nodo_id}'")
            return jsonify({
                "status": "error", 
                "mensaje": "No se pudo enviar el comando (nodo no disponible)"
            }), 500
            
    except Exception as e:
        logger.error(f"Error general en enviar_mensaje: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# FUNCIONES DE CONSOLA Y DEPENDENCIAS
# ============================================

def run_flask():
    """Ejecuta el servidor Flask en un hilo separado"""
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)


def _wire_dependencies():
    """Conecta los módulos entre sí mediante callbacks"""
    net.set_metrics_callback(consolidator.on_metrics_received)
    consolidator.set_db_callback(db.save_metrics)
    monitor.set_last_seen_source(lambda: dict(net.last_seen))
    monitor.set_active_nodes_source(lambda: dict(net.active_nodes))
    monitor.set_status_updater(db.update_node_status)
    net.set_ack_callback(actualizar_ack_callback)
    logger.info("Dependencias inyectadas correctamente.")


# Comandos disponibles para la consola
AVAILABLE_COMMANDS = ["RESCAN", "REBOOT", "STATUS", "LIST", "HELP", "EXIT"]


def _print_help():
    """Muestra los comandos disponibles en la consola"""
    print(
        "\n╔══════════════════════════════════════════╗"
        "\n║        CNS Server — Consola Operator     ║"
        "\n╠══════════════════════════════════════════╣"
        "\n║  LIST              → Listar nodos activos║"
        "\n║  STATUS            → Totales del cluster ║"
        "\n║  RESCAN  <node_id> → Enviar RESCAN       ║"
        "\n║  REBOOT  <node_id> → Enviar REBOOT       ║"
        "\n║  HELP              → Mostrar esta ayuda  ║"
        "\n║  EXIT              → Detener el servidor ║"
        "\n╚══════════════════════════════════════════╝\n"
    )


def _console_worker(loop, stop_event):
    """Hilo que lee comandos del operador por stdin"""
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

        if cmd == "LIST":
            nodes = list(net.active_clients.keys())
            print(f"  Nodos activos ({len(nodes)}): {', '.join(nodes) if nodes else 'ninguno'}")
            logger.info("Consola: LIST → %d nodo(s) activos.", len(nodes))

        elif cmd == "STATUS":
            # Usar el resumen de la API
            try:
                resumen = get_resumen().json
                print(f"\n  Cluster Summary\n"
                      f"  ├─ Nodos activos  : {resumen['nodos_activos']} de 9\n"
                      f"  ├─ Capacidad Total: {resumen['total_capacidad_tb']:.2f} TB\n"
                      f"  ├─ Usado Total    : {resumen['total_usado_tb']:.2f} TB\n"
                      f"  ├─ Libre Total    : {resumen['total_libre_tb']:.2f} TB\n"
                      f"  └─ Uso Global     : {resumen['porcentaje_uso_global']:.2f}%\n")
            except Exception as e:
                print(f"  ✘ Error obteniendo resumen: {e}")

        elif cmd in ("RESCAN", "REBOOT"):
            if not args:
                print(f"  Uso: {cmd} <nodo>")
                continue
            nodo_id = args[0]
            mensaje = " ".join(args[1:]) if len(args) > 1 else f"Operador solicitó {cmd}"
            
            conn = db._get_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id FROM Nodes WHERE identifier = %s", (nodo_id,))
                node = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if node:
                    mensaje_id = guardar_mensaje_db(node["id"], f"{cmd}: {mensaje}")
                else:
                    mensaje_id = None
            else:
                mensaje_id = None
            
            future = asyncio.run_coroutine_threadsafe(
                net.send_command(nodo_id, cmd, mensaje=mensaje, mensaje_id=mensaje_id), 
                loop
            )
            try:
                success = future.result(timeout=5.0)
                if success:
                    print(f"  ✔ Comando '{cmd}' enviado a '{nodo_id}' (id={mensaje_id})")
                else:
                    print(f"  ✘ No se pudo enviar '{cmd}' a '{nodo_id}'")
            except asyncio.TimeoutError:
                print(f"  ✘ Timeout enviando comando a '{nodo_id}'")
            except Exception as e:
                print(f"  ✘ Error: {e}")

        elif cmd == "HELP":
            _print_help()

        elif cmd == "EXIT":
            logger.info("Consola: solicitud de apagado recibida.")
            print("  Deteniendo el servidor CNS...")
            asyncio.run_coroutine_threadsafe(stop_event.wait(), loop)
            break

        else:
            print(f"  Comando desconocido: '{cmd}'. Escribe HELP para ver opciones.")


# ============================================
# MAIN
# ============================================

async def main():
    global event_loop
    
    logger.info("═" * 60)
    logger.info("  CNS Server — Central Node Server arrancando...")
    logger.info("═" * 60)

    _wire_dependencies()

    event_loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ API Flask iniciada en http://0.0.0.0:5001/api")

    monitor_task = asyncio.create_task(monitor.monitor_loop())

    console_thread = threading.Thread(target=_console_worker, args=(event_loop, stop_event), daemon=True)
    console_thread.start()
    logger.info("Consola de comandos iniciada (hilo separado).")

    server_task = asyncio.create_task(net.start_server(host="0.0.0.0", port=5000))

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Apagando servidor...")
        monitor_task.cancel()
        server_task.cancel()
        await asyncio.gather(monitor_task, server_task, return_exceptions=True)
        logger.info("Servidor CNS detenido. Hasta luego.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido por el usuario.")