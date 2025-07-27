# init_db.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from database.connection import Base  # Asegúrate de que Base se importe desde donde la definiste
from database.models import Equipment, Message, Conversation, Quotation # Importa todos tus modelos

# Cargar variables de entorno
load_dotenv()

def create_database_tables():
    """
    Se conecta a la base de datos y crea todas las tablas definidas en los modelos.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: No se encontró la variable de entorno DATABASE_URL.")
        return

    print(f"🔌 Conectando a la base de datos para crear tablas...")
    print(f"   (Host: {db_url.split('@')[-1]})")
    
    try:
        engine = create_engine(db_url)
        print("⏳ Creando todas las tablas definidas en los modelos...")
        
        # Esta es la línea mágica que crea las tablas
        Base.metadata.create_all(bind=engine)
        
        print("✅ ¡Éxito! Todas las tablas han sido creadas en la base de datos.")
    except Exception as e:
        print(f"❌ Error al crear las tablas: {e}")

if __name__ == "__main__":
    create_database_tables()