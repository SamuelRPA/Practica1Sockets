// src/utils/calculosCluster.js
export const calcularMetricasCluster = (nodos) => {
  console.log('📊 calculosCluster.js - nodos recibidos:', nodos);
  
  if (!nodos || nodos.length === 0) {
    console.log('❌ No hay nodos');
    return {
      totalCapacidadTB: 0,
      totalUsadoTB: 0,
      totalLibreTB: 0,
      porcentajeUso: 0,
      nodosActivos: 0,
      totalNodos: 9,
      mensaje: 'Reportaron 0 de 9'
    };
  }

  // Filtrar solo nodos ACTIVOS
  const nodosActivos = nodos.filter(n => n.status === "Activo");
  console.log('📊 Nodos activos:', nodosActivos);
  
  // Calcular totales
  let totalCapacidad = 0;
  let totalUsado = 0;
  let totalLibre = 0;
  
  nodosActivos.forEach(nodo => {
    console.log(`🔍 Procesando ${nodo.display_name}:`, {
      total_gb: nodo.total_gb,
      used_gb: nodo.used_gb,
      free_gb: nodo.free_gb
    });
    
    totalCapacidad += nodo.total_gb || 0;
    totalUsado += nodo.used_gb || 0;
    totalLibre += nodo.free_gb || 0;
  });

  console.log('📊 Totales calculados:', {
    totalCapacidad,
    totalUsado,
    totalLibre
  });

  // Convertir a TB (dividir entre 1000)
  const totalCapacidadTB = (totalCapacidad / 1000).toFixed(2);
  const totalUsadoTB = (totalUsado / 1000).toFixed(2);
  const totalLibreTB = (totalLibre / 1000).toFixed(2);

  // Porcentaje global
  const porcentajeUso = totalCapacidad > 0 
    ? ((totalUsado / totalCapacidad) * 100).toFixed(2)
    : 0;

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