# cleanup_history.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def clear_database_history():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: No se encontró la variable de entorno DATABASE_URL.")
        return

    print(f"🔌 Conectando a la base de datos para limpieza forzada...")
    print(f"   (Host: {db_url.split('@')[-1]})")
    
    # --- SQL commands to completely reset the main tables ---
    # TRUNCATE es más rápido que DELETE y resetea los contadores de ID.
    # CASCADE asegura que si un mensaje depende de una conversación, se borra sin problemas.
    sql_commands = [
        "TRUNCATE TABLE public.messages RESTART IDENTITY CASCADE;",
        "TRUNCATE TABLE public.conversations RESTART IDENTITY CASCADE;"
    ]

    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            trans = connection.begin()
            print("🗑️ Ejecutando limpieza forzada con TRUNCATE...")
            for command in sql_commands:
                try:
                    connection.execute(text(command))
                    print(f"   ✅ Comando ejecutado: {command.split(' ')[1]}")
                except Exception as e:
                    # Esto es esperado si la tabla no existe, lo cual está bien.
                    print(f"   ⚠️  Nota: No se pudo ejecutar '{command.split(' ')[1]}'. Probablemente la tabla no existía, lo cual es correcto en este paso.")
            trans.commit()
        print("✅ Limpieza forzada completada.")
    except Exception as e:
        print(f"❌ Error durante la limpieza forzada: {e}")

if __name__ == "__main__":
    clear_database_history()