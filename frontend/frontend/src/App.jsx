// src/App.jsx
import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import NodoDetalle from './components/NodoDetalle';

function App() {
  const [nodoSeleccionado, setNodoSeleccionado] = useState(null);

  const handleVolver = () => {
    setNodoSeleccionado(null);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {nodoSeleccionado ? (
        <NodoDetalle 
          nodo={nodoSeleccionado} 
          onVolver={handleVolver}
        />
      ) : (
        <Dashboard onSeleccionarNodo={setNodoSeleccionado} />
      )}
    </div>
  );
}

export default App;