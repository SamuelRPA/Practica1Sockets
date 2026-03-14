// src/hooks/useNodoEnTiempoReal.js
import { useState, useEffect } from 'react';

export const useNodoEnTiempoReal = (nodoInicial) => {
  const [nodo, setNodo] = useState(nodoInicial);
  const [discos, setDiscos] = useState(nodoInicial.discos || []);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(new Date());
  const [conectado, setConectado] = useState(nodoInicial.status === 'Activo');

  useEffect(() => {
    let isMounted = true;
    let timeoutId = null;
    
    const actualizarNodo = async () => {
      try {
        const response = await fetch('http://127.0.0.1:5001/api/nodos');
        const nodos = await response.json();
        
        if (!isMounted) return;
        
        const nodoActualizado = nodos.find(n => n.identifier === nodoInicial.identifier);
        
        if (nodoActualizado) {
          setNodo(nodoActualizado);
          setDiscos(nodoActualizado.discos || []);
          setUltimaActualizacion(new Date());
          
          // Detectar si está activo
          const estaActivo = nodoActualizado.status === 'Activo';
          setConectado(estaActivo);
          
          console.log(`🔄 Nodo ${nodoActualizado.identifier} - Estado: ${nodoActualizado.status}`);
        }
      } catch (error) {
        console.error('Error actualizando nodo:', error);
      }
    };

    const intervalId = setInterval(actualizarNodo, 2000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [nodoInicial.identifier]);

  return { nodo, discos, ultimaActualizacion, conectado };
};