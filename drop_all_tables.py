# drop_all_tables.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from database.connection import Base # Importa la Base de tus modelos

# Cargar variables de entorno
load_dotenv()

def drop_database_tables():
    """
    Se conecta a la base de datos y ELIMINA todas las tablas definidas en los modelos.
    ¡¡¡CUIDADO: ESTA ACCIÓN ES IRREVERSIBLE Y BORRARÁ TODOS LOS DATOS!!!
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: No se encontró la variable de entorno DATABASE_URL.")
        return

    print("🔌 Conectando a la base de datos para eliminar tablas...")
    print(f"   (Host: {db_url.split('@')[-1]})")

    # Pedir confirmación para evitar desastres
    confirm = input("⚠️ ¿Estás seguro de que quieres borrar TODAS las tablas y sus datos? Esta acción no se puede deshacer. (escribe 'si' para confirmar): ")
    if confirm.lower() != 'si':
        print("🛑 Operación cancelada por el usuario.")
        return

    try:
        engine = create_engine(db_url)
        print("⏳ Eliminando todas las tablas definidas en los modelos...")
        
        # Esta línea elimina las tablas
        Base.metadata.drop_all(bind=engine)
        
        print("✅ ¡Éxito! Todas las tablas han sido eliminadas de la base de datos.")
    except Exception as e:
        print(f"❌ Error al eliminar las tablas: {e}")

if __name__ == "__main__":
    drop_database_tables()