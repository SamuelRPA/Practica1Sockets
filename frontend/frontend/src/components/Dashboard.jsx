// src/components/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import { getNodos } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { calcularMetricasCluster, obtenerNodosCompletos } from '../utils/calculosCluster';
import ControlAutoRefresh from './ControlAutoRefresh';
import TarjetaNodo from './TarjetaNodo';
import '../css/dashboard.css';

const Dashboard = ({ onSeleccionarNodo }) => {
  const [nodos, setNodos] = useState([]);
  const [cargando, setCargando] = useState(true);

  const cargarDatos = async () => {
    try {
      const nodosData = await getNodos();
      const nodosCompletos = obtenerNodosCompletos(nodosData);
      setNodos(nodosCompletos);
    } catch (error) {
      console.error('Error cargando datos:', error);
    } finally {
      setCargando(false);
    }
  };

  const {
    intervalo,
    setIntervalo,
    activo,
    setActivo,
    ultimaActualizacion,
    actualizarManual
  } = useAutoRefresh(cargarDatos, 30);

  useEffect(() => {
    cargarDatos();
  }, []);

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
          <div className="db-stat-card blue">
            <p className="db-stat-label">Uso Global</p>
            <p className="db-stat-value">{metricasCluster.porcentajeUso}%</p>
          </div>
        </div>
        <p className="db-report-message">{metricasCluster.mensaje}</p>
      </div>

      <ControlAutoRefresh
        intervalo={intervalo}
        setIntervalo={setIntervalo}
        activo={activo}
        setActivo={setActivo}
        ultimaActualizacion={ultimaActualizacion}
        actualizarManual={actualizarManual}
      />

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