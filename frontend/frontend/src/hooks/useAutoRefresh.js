// src/hooks/useAutoRefresh.js - VERSIÓN CORREGIDA
import { useState, useEffect, useCallback, useRef } from 'react';

export const useAutoRefresh = (fetchData, initialInterval = 30) => {
  const [intervalo, setIntervalo] = useState(initialInterval);
  const [activo, setActivo] = useState(true);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(null);
  
  // Usar useRef para mantener la referencia a fetchData sin causar re-renders
  const fetchDataRef = useRef(fetchData);
  
  // Actualizar la referencia cuando cambie fetchData
  useEffect(() => {
    fetchDataRef.current = fetchData;
  }, [fetchData]);

  const actualizar = useCallback(async () => {
    try {
      await fetchDataRef.current();
      setUltimaActualizacion(new Date());
    } catch (error) {
      console.error('Error en actualización automática:', error);
    }
  }, []); // Sin dependencias porque usamos ref

  // Efecto para la actualización inicial
  useEffect(() => {
    actualizar();
  }, [actualizar]);

  // Efecto para el intervalo - AHORA SÍ RESPETA EL INTERVALO
  useEffect(() => {
    if (!activo || intervalo === 0) return;

    console.log(`⏰ Auto-refresh configurado cada ${intervalo} segundos`);
    
    const timer = setInterval(() => {
      actualizar();
    }, intervalo * 1000);

    // Limpiar intervalo cuando cambie intervalo, activo, o se desmonte
    return () => {
      console.log('🛑 Intervalo anterior limpiado');
      clearInterval(timer);
    };
  }, [intervalo, activo, actualizar]); // ✅ DEPENDENCIAS CORRECTAS

  return {
    intervalo,
    setIntervalo,
    activo,
    setActivo,
    ultimaActualizacion,
    actualizarManual: actualizar
  };
};