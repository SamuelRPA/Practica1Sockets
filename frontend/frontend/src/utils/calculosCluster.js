// src/utils/calculosCluster.js
export const calcularMetricasCluster = (nodos) => {
  if (!nodos || nodos.length === 0) {
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

  // Contar nodos activos (los que tienen datos recientes)
  const activos = nodos.filter(n => n.status === 'Activo' && n.total_gb > 0).length;
  
  // Calcular totales
  const totalCapacidad = nodos.reduce((sum, n) => sum + (n.total_gb || 0), 0);
  const totalUsado = nodos.reduce((sum, n) => sum + (n.used_gb || 0), 0);
  const totalLibre = nodos.reduce((sum, n) => sum + (n.free_gb || 0), 0);

  // Convertir a TB para mostrar
  const totalCapacidadTB = totalCapacidad / 1000;
  const totalUsadoTB = totalUsado / 1000;
  const totalLibreTB = totalLibre / 1000;

  // Porcentaje global
  const porcentajeUso = totalCapacidad > 0 
    ? ((totalUsado / totalCapacidad) * 100).toFixed(2)
    : 0;

  return {
    totalCapacidadTB: totalCapacidadTB.toFixed(2),
    totalUsadoTB: totalUsadoTB.toFixed(2),
    totalLibreTB: totalLibreTB.toFixed(2),
    porcentajeUso,
    nodosActivos: activos,
    totalNodos: 9,
    mensaje: `Reportaron ${activos} de 9`
  };
};

export const obtenerNodosCompletos = (nodos) => {
  // Lista fija de los 9 nodos requeridos
  const todosLosNodos = [
    { identifier: 'lapaz', display_name: 'La Paz' },
    { identifier: 'cochabamba', display_name: 'Cochabamba' },
    { identifier: 'santacruz', display_name: 'Santa Cruz' },
    { identifier: 'oruro', display_name: 'Oruro' },
    { identifier: 'potosi', display_name: 'Potosí' },
    { identifier: 'chuquisaca', display_name: 'Chuquisaca' },
    { identifier: 'tarija', display_name: 'Tarija' },
    { identifier: 'beni', display_name: 'Beni' },
    { identifier: 'pando', display_name: 'Pando' }
  ];

  // Mapear los nodos existentes
  return todosLosNodos.map(nodoInfo => {
    const existente = nodos.find(n => n.identifier === nodoInfo.identifier);
    
    if (existente) {
      return {
        ...existente,
        display_name: nodoInfo.display_name // Asegurar nombre bonito
      };
    }

    // Nodo que no reporta
    return {
      identifier: nodoInfo.identifier,
      display_name: nodoInfo.display_name,
      total_gb: 0,
      used_gb: 0,
      free_gb: 0,
      iops: 0,
      disk_type: 'N/A',
      ram_gb: 0,
      status: 'No Reporta',
      last_seen: null
    };
  });
};