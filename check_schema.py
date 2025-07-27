# check_schema.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()

def check_database_schema():
    """
    Verifica el esquema actual de la base de datos
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: No se encontró la variable de entorno DATABASE_URL.")
        return

    print(f"🔌 Conectando a la base de datos para verificar esquema...")
    print(f"   (Host: {db_url.split('@')[-1]})")
    
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Verificar si existe la tabla conversations
        if 'conversations' in inspector.get_table_names(schema='public'):
            print("\n📋 Tabla 'conversations' encontrada.")
            columns = inspector.get_columns('conversations', schema='public')
            
            print("\n🏗️ Columnas actuales en 'conversations':")
            for column in columns:
                print(f"   - {column['name']}: {column['type']} {'(nullable)' if column['nullable'] else '(NOT NULL)'}")
                
            # Verificar si user_id existe
            column_names = [col['name'] for col in columns]
            if 'user_id' not in column_names:
                print("\n❌ PROBLEMA ENCONTRADO: La columna 'user_id' NO existe en la tabla conversations")
                print("   Necesitas agregar esta columna o recrear la tabla.")
            else:
                print("\n✅ La columna 'user_id' existe correctamente.")
                
        else:
            print("\n❌ La tabla 'conversations' NO existe en el esquema 'public'")
            
        # Verificar otras tablas importantes
        print("\n📊 Todas las tablas en el esquema 'public':")
        tables = inspector.get_table_names(schema='public')
        for table in tables:
            print(f"   - {table}")
            
    except Exception as e:
        print(f"❌ Error verificando esquema: {e}")

if __name__ == "__main__":
    check_database_schema()