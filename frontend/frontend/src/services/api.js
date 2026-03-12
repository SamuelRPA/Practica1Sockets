const API_URL = 'http://127.0.0.1:5001/api';  // ← USA ESTA URL

export const getNodos = async () => {
  try {
    const response = await fetch(`${API_URL}/nodos`);
    if (!response.ok) throw new Error('Error');
    return await response.json();
  } catch (error) {
    console.error('Error:', error);
    return [];
  }
};

export const getResumenCluster = async () => {
  try {
    const response = await fetch(`${API_URL}/cluster/resumen`);
    return await response.json();
  } catch (error) {
    console.error('Error:', error);
    return {
      total_capacidad_tb: 0,
      total_usado_tb: 0,
      total_libre_tb: 0,
      nodos_activos: 0,
      total_nodos: 9,
      porcentaje_uso_global: 0
    };
  }
};

export const getHistorialNodo = async (nodoId) => {
  try {
    const response = await fetch(`${API_URL}/nodos/${nodoId}/historial`);
    if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Error en getHistorial:', error);
    return [];
  }
};

export const enviarComando = async (nodoId, comando, mensaje = '') => {
  try {
    const response = await fetch(`${API_URL}/mensajes/${nodoId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comando, mensaje })
    });
    if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Error en enviarComando:', error);
    return { status: 'error', mensaje: error.message };
  }
};