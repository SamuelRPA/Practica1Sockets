// src/utils/calculosCluster.js
export const calcularMetricasCluster = (nodos) => {
  console.log('📊 calculosCluster.js - nodos recibidos:', nodos);
  
  if (!nodos || nodos.length === 0) {
    return {
      totalCapacidadTB: '0.00',
      totalUsadoTB: '0.00',
      totalLibreTB: '0.00',
      porcentajeUso: '0',
      nodosActivos: 0,
      totalNodos: 9,
      mensaje: 'Reportaron 0 de 9'
    };
  }

  // Filtrar solo nodos ACTIVOS
  const nodosActivos = nodos.filter(n => n.status === "Activo");
  console.log('📊 Nodos activos:', nodosActivos);
  
  // Calcular totales SOLO de nodos activos
  let totalCapacidad = 0;
  let totalUsado = 0;
  let totalLibre = 0;
  
  nodosActivos.forEach(nodo => {
    console.log(`🔍 Procesando ${nodo.display_name} (ACTIVO):`, {
      total_gb: nodo.total_gb,
      used_gb: nodo.used_gb,
      free_gb: nodo.free_gb
    });
    
    totalCapacidad += nodo.total_gb || 0;
    totalUsado += nodo.used_gb || 0;
    totalLibre += nodo.free_gb || 0;
  });

  console.log('📊 Totales calculados (solo activos):', {
    totalCapacidad,
    totalUsado,
    totalLibre
  });

  // Convertir a TB (dividir entre 1000)
  const totalCapacidadTB = totalCapacidad > 0 ? (totalCapacidad / 1000).toFixed(2) : '0.00';
  const totalUsadoTB = totalUsado > 0 ? (totalUsado / 1000).toFixed(2) : '0.00';
  const totalLibreTB = totalLibre > 0 ? (totalLibre / 1000).toFixed(2) : '0.00';

  // Porcentaje global - si no hay activos, mostrar 0
  const porcentajeUso = totalCapacidad > 0 
    ? ((totalUsado / totalCapacidad) * 100).toFixed(2)
    : '0';

  return {
    totalCapacidadTB,
    totalUsadoTB,
    totalLibreTB,
    porcentajeUso,
    nodosActivos: nodosActivos.length,
    totalNodos: 9,
    mensaje: `Reportaron ${nodosActivos.length} de 9`
  };
};