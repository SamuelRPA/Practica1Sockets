// src/components/Dashboard.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getNodos } from '../services/api';
import { calcularMetricasCluster } from '../utils/calculosCluster';
import { useTarjetasEnTiempoReal } from '../hooks/useTarjetasEnTiempoReal';
import TarjetaNodo from './TarjetaNodo';
import '../css/dashboard.css';

const Dashboard = ({ onSeleccionarNodo }) => {
  const [nodosIniciales, setNodosIniciales] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(null);

  // Usar el hook que se actualiza cada 5 segundos
  const nodos = useTarjetasEnTiempoReal(nodosIniciales);

  const cargarDatos = useCallback(async () => {
    try {
      const data = await getNodos();
      setNodosIniciales(data);
      setUltimaActualizacion(new Date());
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarDatos();
    
    const intervalo = setInterval(cargarDatos, 15000); // 15 segundos sin contador visible
    
    return () => {
      clearInterval(intervalo);
    };
  }, [cargarDatos]);

  const metricasCluster = calcularMetricasCluster(nodos);

  if (cargando) return <div className="db-container">Cargando...</div>;

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
        {nodos.map((nodo) => (
          <TarjetaNodo
            key={nodo.identifier}
            nodo={nodo}
            onClick={onSeleccionarNodo}
          />
        ))}
      </div>
    </div>
  );
};

export default Dashboard;