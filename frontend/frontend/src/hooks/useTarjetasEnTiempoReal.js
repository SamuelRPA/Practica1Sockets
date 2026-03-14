// src/hooks/useTarjetasEnTiempoReal.js
import { useState, useEffect } from 'react';

export const useTarjetasEnTiempoReal = (nodosIniciales) => {
  const [nodos, setNodos] = useState(nodosIniciales);

  useEffect(() => {
    let isMounted = true;
    
    const actualizarTarjetas = async () => {
      try {
        const response = await fetch('http://127.0.0.1:5001/api/nodos');
        const nuevosNodos = await response.json();
        
        if (!isMounted) return;
        
        // Forzar actualización aunque los datos sean iguales
        setNodos([...nuevosNodos]); // Crear nuevo array para forzar render
        
        const activos = nuevosNodos.filter(n => n.status === 'Activo').length;
        console.log(`📊 Tarjetas actualizadas: ${activos} activos de ${nuevosNodos.length}`);
        
      } catch (error) {
        console.error('Error actualizando tarjetas:', error);
      }
    };

    const intervalId = setInterval(actualizarTarjetas, 5000); // Cada 5 segundos

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  return nodos;
};