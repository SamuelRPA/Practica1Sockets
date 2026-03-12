// src/components/TarjetaNodo.jsx
import React from 'react';
import '../css/tarjetaNodo.css';

const TarjetaNodo = ({ nodo, onClick }) => {
  const isActivo = nodo.status === 'Activo' && nodo.total_gb > 0;
  const porcentajeUso = isActivo ? ((nodo.used_gb / nodo.total_gb) * 100).toFixed(1) : 0;

  return (
    <div
      onClick={() => isActivo && onClick(nodo)}
      className={`tj-card ${isActivo ? 'activo' : 'inactivo'}`}
    >
      <div className="tj-header">
        <h3 className="tj-nombre">{nodo.display_name}</h3>
        <span className={`tj-estado ${isActivo ? 'activo' : 'inactivo'}`}>
          {isActivo ? 'Activo' : 'No Reporta'}
        </span>
      </div>

      {isActivo ? (
        <>
          <div className="tj-stats-grid">
            <div>
              <p className="tj-stat">Total</p>
              <p className="tj-stat-value">{(nodo.total_gb / 1000).toFixed(2)} TB</p>
            </div>
            <div>
              <p className="tj-stat">Usado</p>
              <p className="tj-stat-value">{(nodo.used_gb / 1000).toFixed(2)} TB</p>
            </div>
            <div>
              <p className="tj-stat">Libre</p>
              <p className="tj-stat-value">{(nodo.free_gb / 1000).toFixed(2)} TB</p>
            </div>
            <div>
              <p className="tj-stat">RAM</p>
              <p className="tj-stat-value">{nodo.ram_gb} GB</p>
            </div>
          </div>

          <div className="tj-progress-container">
            <div 
              className="tj-progress-bar" 
              style={{ width: `${porcentajeUso}%` }}
            ></div>
          </div>
          <p className="tj-progress-label">{porcentajeUso}% usado</p>
        </>
      ) : (
        <p className="tj-empty">Sin datos recientes</p>
      )}
    </div>
  );
};

export default TarjetaNodo;