// src/components/Dashboard.jsx - VERSIÓN DE PRUEBA
import React, { useState, useEffect } from 'react';
import { getNodos } from '../services/api';
import { calcularMetricasCluster } from '../utils/calculosCluster';
import TarjetaNodo from './TarjetaNodo';
import '../css/dashboard.css';

const Dashboard = ({ onSeleccionarNodo }) => {
  const [nodos, setNodos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(null);

  useEffect(() => {
    cargarDatos();
    const intervalo = setInterval(cargarDatos, 10000);
    return () => clearInterval(intervalo);
  }, []);

  const cargarDatos = async () => {
    try {
      console.log('🔄 Cargando datos...');
      const data = await getNodos();
      console.log('📊 Datos recibidos:', data);
      setNodos(data);
      setUltimaActualizacion(new Date());
    } catch (error) {
      console.error('❌ Error:', error);
    } finally {
      setCargando(false);
    }
  };

  const metricasCluster = calcularMetricasCluster(nodos);

  if (cargando) {
    return <div className="db-container">Cargando...</div>;
  }

  return (
    <div className="db-container">
      <div className="db-header">
        <h1 className="db-title">Monitor Nacional de Almacenamiento</h1>
        <div className="db-stats-grid">
          <div className="db-stat-card blue">
            <p className="db-stat-label">Capacidad Total</p>
            <p className="db-stat-value">{metricasCluster.totalCapacidadTB} TB</p>
          </div>
          <div className="db-stat-card yellow">
            <p className="db-stat-label">Espacio Usado</p>
            <p className="db-stat-value">{metricasCluster.totalUsadoTB} TB</p>
          </div>
          <div className="db-stat-card green">
            <p className="db-stat-label">Espacio Libre</p>
            <p className="db-stat-value">{metricasCluster.totalLibreTB} TB</p>
          </div>
          <div className="db-stat-card purple">
            <p className="db-stat-label">Uso Global</p>
            <p className="db-stat-value">{metricasCluster.porcentajeUso}%</p>
          </div>
        </div>
        <p className="db-report-message">{metricasCluster.mensaje}</p>
        {ultimaActualizacion && (
          <p className="db-timestamp">
            Última actualización: {ultimaActualizacion.toLocaleTimeString()}
          </p>
        )}
      </div>

      <div className="db-nodos-grid">
        {nodos.length > 0 ? (
          nodos.map((nodo) => (
            <TarjetaNodo
              key={nodo.identifier}
              nodo={nodo}
              onClick={onSeleccionarNodo}
            />
          ))
        ) : (
          <p>No hay nodos para mostrar</p>
        )}
      </div>
    </div>
  );
};

export default Dashboard;