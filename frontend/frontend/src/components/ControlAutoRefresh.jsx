import React from 'react';
import '../css/controlAutoRefresh.css';  // ← Importas el CSS

const ControlAutoRefresh = ({ 
  intervalo, 
  setIntervalo, 
  activo, 
  setActivo, 
  ultimaActualizacion,
  actualizarManual 
}) => {
  return (
    <div className="ar-contenedor">
      <div className="ar-controls">
        <div className="ar-left">
          {/* Checkbox para activar/desactivar */}
          <label className="ar-checkbox-label">
            <input
              type="checkbox"
              checked={activo}
              onChange={(e) => setActivo(e.target.checked)}
              className="ar-checkbox"
            />
            <span className='ar-span'>Auto-refresh</span>
          </label>

          {/* Selector de intervalo */}
          <select
            value={intervalo}
            onChange={(e) => setIntervalo(Number(e.target.value))}
            disabled={!activo}
            className="ar-select"
          >
            <option value={5}>5 segundos</option>
            <option value={10}>10 segundos</option>
            <option value={30}>30 segundos</option>
            <option value={60}>1 minuto</option>
            <option value={300}>5 minutos</option>
          </select>

          {/* Botón manual */}
          <button
            onClick={actualizarManual}
            className="ar-boton"
          >
            Actualizar ahora
          </button>
        </div>

        {/* Última actualización */}
        {ultimaActualizacion && (
          <p className="ar-timestamp">
            Última actualización: {ultimaActualizacion.toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
};

export default ControlAutoRefresh;