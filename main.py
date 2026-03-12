"""
main.py
Punto de entrada del CNS Server (Central Monitoring Server).
VERSIÓN CON API HTTP PARA DASHBOARD REACT
"""

import asyncio
import threading
from datetime import datetime
from flask import Flask, jsonify
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

# ── Crear API Flask para React ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

@app.route('/api/nodos', methods=['GET'])
def get_nodos():
    try:
        nodos_memoria = []
        for nodo_id, data in net.active_nodes.items():
            nodos_memoria.append({
                "identifier": nodo_id,
                "display_name": data.get("display_name", nodo_id),
                "total_gb": data.get("total_gb", 0),
                "used_gb": data.get("used_gb", 0),
                "free_gb": data.get("free_gb", 0),
                "iops": data.get("iops", 0),
                "disk_type": data.get("disk_type", "HDD"),
                "ram_gb": data.get("ram_gb", 0),
                "status": "Activo",
                "last_seen": data.get("ts", datetime.utcnow()).isoformat() if data.get("ts") else None
            })
        
        if not nodos_memoria:
            resumen = db.get_cluster_summary()
            return jsonify(resumen.get('nodes', []))
        
        return jsonify(nodos_memoria)
    except Exception as e:
        logger.error(f"Error en /api/nodos: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cluster/resumen', methods=['GET'])
def get_resumen():
    try:
        activos = list(net.active_nodes.keys())
        flagged = monitor.get_flagged_nodes()
        totals = consolidator.get_cluster_totals(exclude=set(flagged))
        
        if totals['capacity_total'] == 0:
            resumen = db.get_cluster_summary()
            return jsonify({
                'total_capacidad_tb': resumen.get('capacity_total', 0) / 1000,
                'total_usado_tb': resumen.get('used_total', 0) / 1000,
                'total_libre_tb': resumen.get('free_total', 0) / 1000,
                'nodos_activos': len(activos),
                'total_nodos': 9,
                'porcentaje_uso_global': (resumen.get('used_total', 0) / resumen.get('capacity_total', 1) * 100) if resumen.get('capacity_total', 0) > 0 else 0,
            })
        
        return jsonify({
            'total_capacidad_tb': totals['capacity_total'] / 1000,
            'total_usado_tb': totals['used_total'] / 1000,
            'total_libre_tb': totals['free_total'] / 1000,
            'nodos_activos': len(activos),
            'total_nodos': 9,
            'porcentaje_uso_global': (totals['used_total'] / totals['capacity_total'] * 100) if totals['capacity_total'] > 0 else 0,
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
        
        # Consulta adaptada a tu estructura de BD
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
        
        # Formatear fechas a ISO string
        for row in rows:
            if row["timestamp"]:
                row["timestamp"] = row["timestamp"].isoformat()
        
        logger.info(f"Historial para {nodo_id}: {len(rows)} registros encontrados")
        return jsonify(rows)
        
    except Exception as e:
        logger.error(f"Error en historial de {nodo_id}: {e}")
        return jsonify({"error": str(e)}), 500 
def run_flask():
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

# ── Funciones de consola y dependencias (mantén tu código existente) ──────────
# Asegúrate de que _wire_dependencies(), _console_worker() y main() estén aquí
# Copia estas funciones de tu archivo original

def _wire_dependencies():
    net.set_metrics_callback(consolidator.on_metrics_received)
    consolidator.set_db_callback(db.save_metrics)
    monitor.set_last_seen_source(lambda: dict(net.last_seen))
    monitor.set_active_nodes_source(lambda: dict(net.active_nodes))
    monitor.set_status_updater(db.update_node_status)
    logger.info("Dependencias inyectadas correctamente.")

def _console_worker(loop, stop_event):
    # ... (tu código de consola existente)
    pass

async def main():
    logger.info("═" * 60)
    logger.info("  CNS Server — Central Node Server arrancando...")
    logger.info("═" * 60)

    _wire_dependencies()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # Iniciar Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ API Flask iniciada en http://0.0.0.0:5001/api")

    # Iniciar monitor
    monitor_task = asyncio.create_task(monitor.monitor_loop())

    # Iniciar consola
    console_thread = threading.Thread(target=_console_worker, args=(loop, stop_event), daemon=True)
    console_thread.start()

    # Iniciar servidor TCP
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor detenido.")