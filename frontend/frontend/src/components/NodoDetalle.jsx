// src/components/NodoDetalle.jsx
import React, { useState, useEffect } from 'react';
import { getHistorialNodo, enviarComando } from '../services/api';
import '../css/NodoDetalle.css';

const NodoDetalle = ({ nodo, onVolver }) => {
  const [historial, setHistorial] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [mensajeEnvio, setMensajeEnvio] = useState('');
  const [errorHistorial, setErrorHistorial] = useState('');

  useEffect(() => {
    cargarHistorial();
  }, [nodo.identifier]);

  const cargarHistorial = async () => {
    setCargando(true);
    setErrorHistorial('');
    try {
      const data = await getHistorialNodo(nodo.identifier);
      if (Array.isArray(data) && data.length > 0) {
        setHistorial(data);
      } else {
        setHistorial([]);
        setErrorHistorial('No hay datos históricos disponibles');
      }
    } catch (error) {
      console.error('Error cargando historial:', error);
      setErrorHistorial('Error al cargar el historial');
    } finally {
      setCargando(false);
    }
  };

  const handleEnviarComando = async (comando) => {
    setEnviando(true);
    try {
      const resultado = await enviarComando(nodo.identifier, comando);
      if (resultado.status === 'enviado') {
        setMensajeEnvio(`✅ Comando "${comando}" enviado correctamente`);
      } else {
        setMensajeEnvio(`❌ Error: ${resultado.mensaje || 'No se pudo enviar'}`);
      }
    } catch (error) {
      setMensajeEnvio(`❌ Error: ${error.message}`);
    } finally {
      setEnviando(false);
      setTimeout(() => setMensajeEnvio(''), 3000);
    }
  };

  const isActivo = nodo.status === 'Activo' && nodo.total_gb > 0;
  const porcentajeUso = isActivo ? ((nodo.used_gb / nodo.total_gb) * 100).toFixed(1) : 0;

  // Función para determinar clase de color según porcentaje
  const getBarraClass = (porcentaje) => {
    if (porcentaje > 80) return 'nd-historial-barra-roja';
    if (porcentaje > 60) return 'nd-historial-barra-amarilla';
    return 'nd-historial-barra-verde';
  };

  return (
    <div className="nd-container">
      <button onClick={onVolver} className="nd-back-button">
        ← Volver al Dashboard
      </button>

      <div className="nd-card">
        <div className="nd-header">
          <h2 className="nd-title">{nodo.display_name}</h2>
          <span className={`nd-status-badge ${isActivo ? 'activo' : 'inactivo'}`}>
            {nodo.status}
          </span>
        </div>

        <div className="nd-stats-grid">
          <div className="nd-stat-card blue">
            <p className="nd-stat-label">Total Disco</p>
            <p className="nd-stat-value">{(nodo.total_gb / 1000).toFixed(2)} TB</p>
          </div>
          <div className="nd-stat-card yellow">
            <p className="nd-stat-label">Usado</p>
            <p className="nd-stat-value">{(nodo.used_gb / 1000).toFixed(2)} TB</p>
          </div>
          <div className="nd-stat-card green">
            <p className="nd-stat-label">Libre</p>
            <p className="nd-stat-value">{(nodo.free_gb / 1000).toFixed(2)} TB</p>
          </div>
          <div className="nd-stat-card purple">
            <p className="nd-stat-label">RAM</p>
            <p className="nd-stat-value">{nodo.ram_gb} GB</p>
          </div>
        </div>

        <div className="nd-progress-container">
          <div className="nd-progress-header">
            <span className="nd-progress-header-text">Uso del disco</span>
            <span className="nd-progress-header-porcentaje">{porcentajeUso}%</span>
          </div>
          <div className="nd-progress-bar-bg">
            <div className="nd-progress-bar-fill" style={{ width: `${porcentajeUso}%` }}></div>
          </div>
        </div>

        <div className="nd-info-grid">
          <div className="nd-info-item">
            <p className="nd-info-label">Tipo de disco:</p>
            <p className="nd-info-value">{nodo.disk_type || 'N/A'}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">IOPS:</p>
            <p className="nd-info-value">{nodo.iops || 'N/A'}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">IP Origen:</p>
            <p className="nd-info-value">{nodo.ip_origen || 'N/A'}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">MAC:</p>
            <p className="nd-info-value">{nodo.mac_origen || 'N/A'}</p>
          </div>
        </div>
      </div>

      <div className="nd-commands-section">
        <h3 className="nd-commands-title">Enviar comandos al nodo</h3>
        
        {mensajeEnvio && (
          <div className="nd-message">{mensajeEnvio}</div>
        )}

        <div className="nd-commands-grid">
          <button
            onClick={() => handleEnviarComando('REBOOT')}
            disabled={enviando || !isActivo}
            className="nd-command-button yellow"
          >
            Reiniciar equipo
          </button>
          <button
            onClick={() => handleEnviarComando('ALMACENAMIENTO_COMPLETO')}
            disabled={enviando || !isActivo}
            className="nd-command-button red"
          >
            Almacenamiento completo
          </button>
          <button
            onClick={() => handleEnviarComando('CONFIGURACION')}
            disabled={enviando || !isActivo}
            className="nd-command-button blue"
          >
            Configuración
          </button>
        </div>
      </div>

      {/* HISTORIAL MEJORADO - VERSIÓN CORREGIDA SIN TAILWIND */}
      <div className="nd-historial-section">
        <h3 className="nd-historial-title">Historial de uso del disco</h3>
        
        {cargando ? (
          <p className="nd-historial-mensaje nd-historial-cargando">Cargando historial...</p>
        ) : errorHistorial ? (
          <p className="nd-historial-mensaje nd-historial-error">{errorHistorial}</p>
        ) : historial.length > 0 ? (
          <div className="nd-historial-tabla-container">
            <table className="nd-historial-tabla">
              <thead>
                <tr className="nd-historial-tabla-header">
                  <th className="nd-historial-tabla-th">Fecha y Hora</th>
                  <th className="nd-historial-tabla-th">Total (GB)</th>
                  <th className="nd-historial-tabla-th">Usado (GB)</th>
                  <th className="nd-historial-tabla-th">Libre (GB)</th>
                  <th className="nd-historial-tabla-th">% Uso</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((item, index) => {
                  const fecha = new Date(item.timestamp);
                  const porcentaje = ((item.used_gb / item.total_gb) * 100).toFixed(2);
                  
                  return (
                    <tr key={index} className="nd-historial-tabla-fila">
                      <td className="nd-historial-tabla-td nd-historial-fecha">
                        {fecha.toLocaleDateString('es-ES', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit'
                        })}
                      </td>
                      <td className="nd-historial-tabla-td nd-historial-numero">
                        {item.total_gb.toFixed(2)} GB
                      </td>
                      <td className="nd-historial-tabla-td nd-historial-numero">
                        <span className="nd-historial-usado">{item.used_gb.toFixed(2)} GB</span>
                        <span className="nd-historial-porcentaje">({porcentaje}%)</span>
                      </td>
                      <td className="nd-historial-tabla-td nd-historial-numero">
                        {item.free_gb.toFixed(2)} GB
                      </td>
                      <td className="nd-historial-tabla-td">
                        <div className="nd-historial-barra-contenedor">
                          <div className="nd-historial-barra">
                            <div 
                              className={`nd-historial-barra-progreso ${getBarraClass(porcentaje)}`}
                              style={{ width: `${porcentaje}%` }}
                            ></div>
                          </div>
                          <span className="nd-historial-barra-porcentaje">{porcentaje}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="nd-historial-mensaje nd-historial-vacio">No hay historial disponible</p>
        )}
      </div>
    </div>
  );
};

export default NodoDetalle;