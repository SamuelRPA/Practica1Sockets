// src/components/NodoDetalle.jsx
import React, { useState, useEffect } from 'react';
import { getHistorialNodo, enviarComando } from '../services/api';
import { useNodoEnTiempoReal } from '../hooks/useNodoEnTiempoReal';
import '../css/NodoDetalle.css';

const NodoDetalle = ({ nodo: nodoInicial, onVolver }) => {
  const [historial, setHistorial] = useState([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [mensajeEnvio, setMensajeEnvio] = useState('');
  const [errorHistorial, setErrorHistorial] = useState('');
  const [discoSeleccionado, setDiscoSeleccionado] = useState(0);
  const [contadorHistorial, setContadorHistorial] = useState(5); // Contador para historial
  
  // Usar el hook de tiempo real
  const { nodo, discos, ultimaActualizacion } = useNodoEnTiempoReal(nodoInicial);

  // Cargar historial al montar y cada 5 segundos
  useEffect(() => {
    cargarHistorial();
    
    // Actualizar historial cada 5 segundos
    const intervaloHistorial = setInterval(() => {
      cargarHistorial();
    }, 20000);
    
    // Contador regresivo para el historial
    const contador = setInterval(() => {
      setContadorHistorial(prev => {
        if (prev <= 1) {
          return 20; // Reiniciar cuando llegue a 0
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => {
      clearInterval(intervaloHistorial);
      clearInterval(contador);
    };
  }, [nodo.identifier]);

  const cargarHistorial = async () => {
    setCargandoHistorial(true);
    setErrorHistorial('');
    try {
      const data = await getHistorialNodo(nodo.identifier);
      console.log('📊 Historial recibido:', data);
      
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
      setCargandoHistorial(false);
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

  const isActivo = nodo.status === 'Activo';
  
  // Usar los discos del hook (actualizados en tiempo real)
  const discosActuales = discos.length > 0 ? discos : (nodo.discos || []);
  const cantidadDiscos = discosActuales.length || 1;
  
  const discoActual = discosActuales[discoSeleccionado] || {
    nombre: 'C:',
    total_gb: nodo.total_gb || 0,
    used_gb: nodo.used_gb || 0,
    free_gb: nodo.free_gb || 0,
    tipo: nodo.disk_type || 'N/A',
    iops: nodo.iops || 0
  };
  
  const porcentajeUso = discoActual.total_gb > 0 
    ? ((discoActual.used_gb / discoActual.total_gb) * 100).toFixed(1) 
    : 0;

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

      {/* Indicador de actualización en tiempo real */}
      <div className="nd-actualizacion">
        <span className="nd-actualizacion-icono">🔄</span>
        <span className="nd-actualizacion-texto">
          Nodo actualizado: {ultimaActualizacion.toLocaleTimeString()}
          {cantidadDiscos > 0 && ` • ${cantidadDiscos} disco(s)`}
        </span>
      </div>

      <div className="nd-card">
        <div className="nd-header">
          <h2 className="nd-title">{nodo.display_name}</h2>
          <span className={`nd-status-badge ${isActivo ? 'activo' : 'inactivo'}`}>
            {nodo.status}
          </span>
        </div>

        {/* Selector de discos (si hay múltiples) */}
        {discosActuales.length > 1 && (
          <div className="nd-selector-discos">
            <p className="nd-selector-label">
              Discos disponibles ({cantidadDiscos}):
            </p>
            <div className="nd-selector-botones">
              {discosActuales.map((disco, index) => (
                <button
                  key={index}
                  className={`nd-selector-boton ${index === discoSeleccionado ? 'activo' : ''}`}
                  onClick={() => setDiscoSeleccionado(index)}
                >
                  {disco.nombre} ({disco.total_gb} GB - {disco.tipo})
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Información del disco seleccionado */}
        <div className="nd-stats-grid">
          <div className="nd-stat-card blue">
            <p className="nd-stat-label">Disco {discoActual.nombre}</p>
            <p className="nd-stat-value">{discoActual.total_gb?.toFixed(2) || 0} GB</p>
          </div>
          <div className="nd-stat-card yellow">
            <p className="nd-stat-label">Usado</p>
            <p className="nd-stat-value">{discoActual.used_gb?.toFixed(2) || 0} GB</p>
          </div>
          <div className="nd-stat-card green">
            <p className="nd-stat-label">Libre</p>
            <p className="nd-stat-value">{discoActual.free_gb?.toFixed(2) || 0} GB</p>
          </div>
          <div className="nd-stat-card purple">
            <p className="nd-stat-label">Tipo</p>
            <p className="nd-stat-value">{discoActual.tipo || 'N/A'}</p>
          </div>
        </div>

        <div className="nd-progress-container">
          <div className="nd-progress-header">
            <span className="nd-progress-header-text">Uso del disco {discoActual.nombre}</span>
            <span className="nd-progress-header-porcentaje">{porcentajeUso}%</span>
          </div>
          <div className="nd-progress-bar-bg">
            <div className="nd-progress-bar-fill" style={{ width: `${porcentajeUso}%` }}></div>
          </div>
        </div>

        {/* Información general del nodo */}
        <div className="nd-info-grid">
          <div className="nd-info-item">
            <p className="nd-info-label">Total discos:</p>
            <p className="nd-info-value">{cantidadDiscos}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">Total capacidad:</p>
            <p className="nd-info-value">{(nodo.total_gb || 0).toFixed(2)} GB</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">Total usado:</p>
            <p className="nd-info-value">{(nodo.used_gb || 0).toFixed(2)} GB</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">Total libre:</p>
            <p className="nd-info-value">{(nodo.free_gb || 0).toFixed(2)} GB</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">IP:</p>
            <p className="nd-info-value">{nodo.ip || nodo.ip_origen || 'N/A'}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">MAC:</p>
            <p className="nd-info-value">{nodo.mac || nodo.mac_origen || 'N/A'}</p>
          </div>
          <div className="nd-info-item">
            <p className="nd-info-label">RAM:</p>
            <p className="nd-info-value">{nodo.ram_gb || 0} GB</p>
          </div>
          <div className="nd-info-item nd-info-item-full">
            <p className="nd-info-label">Última actualización:</p>
            <p className="nd-info-value">
              {nodo.last_seen ? new Date(nodo.last_seen).toLocaleString() : 'N/A'}
            </p>
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

      {/* HISTORIAL CON CONTADOR */}
      <div className="nd-historial-section">
        <div className="nd-historial-header">
          <h3 className="nd-historial-title">Historial de uso</h3>
          <div className="nd-historial-contador">
            <span className="nd-historial-contador-label">Actualizando en:</span>
            <span className={`nd-historial-contador-valor ${contadorHistorial <= 3 ? 'finalizando' : ''}`}>
              {contadorHistorial}s
            </span>
          </div>
        </div>
        
        {cargandoHistorial ? (
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