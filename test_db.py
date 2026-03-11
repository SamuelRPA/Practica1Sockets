from server.database.db_manager import DBManager

print("🔌 Intentando conectar a Railway...")
try:
    db = DBManager()
    # Verificamos si el pool se creó (eso significa que conectó)
    if db._pool is not None:
        print("✅ ¡CONEXIÓN EXITOSA! Tu servidor ya puede escribir en la nube.")
    else:
        print("❌ Error: No se pudo crear el pool. Revisa tu password.")
except Exception as e:
    print(f"💥 Ocurrió un error inesperado: {e}")