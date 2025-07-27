# fix_database.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def fix_database_schema():
    """
    Repara el esquema de la base de datos añadiendo las columnas faltantes
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: No se encontró la variable de entorno DATABASE_URL.")
        return

    print(f"🔧 Conectando a la base de datos para reparar esquema...")
    print(f"   (Host: {db_url.split('@')[-1]})")
    
    # Lista de comandos SQL para reparar la tabla
    repair_commands = [
        # Agregar columna user_id si no existe
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'user_id') THEN
                ALTER TABLE public.conversations ADD COLUMN user_id VARCHAR(50);
                RAISE NOTICE 'Columna user_id agregada a conversations';
            ELSE
                RAISE NOTICE 'Columna user_id ya existe en conversations';
            END IF;
        END $$;
        """,
        
        # Agregar otras columnas que podrían faltar
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'user_name') THEN
                ALTER TABLE public.conversations ADD COLUMN user_name VARCHAR(255);
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'company_name') THEN
                ALTER TABLE public.conversations ADD COLUMN company_name VARCHAR(255);
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'phone') THEN
                ALTER TABLE public.conversations ADD COLUMN phone VARCHAR(50);
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'email') THEN
                ALTER TABLE public.conversations ADD COLUMN email VARCHAR(255);
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'project_details') THEN
                ALTER TABLE public.conversations ADD COLUMN project_details JSON;
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'recommended_equipment') THEN
                ALTER TABLE public.conversations ADD COLUMN recommended_equipment JSON;
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'stage') THEN
                ALTER TABLE public.conversations ADD COLUMN stage VARCHAR(50) DEFAULT 'welcome';
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'documents') THEN
                ALTER TABLE public.conversations ADD COLUMN documents JSON;
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'quotation_sent') THEN
                ALTER TABLE public.conversations ADD COLUMN quotation_sent BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'commercial_notified') THEN
                ALTER TABLE public.conversations ADD COLUMN commercial_notified BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'created_at') THEN
                ALTER TABLE public.conversations ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            END IF;
        END $$;
        """,
        
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_schema = 'public' 
                          AND table_name = 'conversations' 
                          AND column_name = 'updated_at') THEN
                ALTER TABLE public.conversations ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
        """
    ]
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            trans = connection.begin()
            print("🔧 Ejecutando reparaciones del esquema...")
            
            for i, command in enumerate(repair_commands, 1):
                try:
                    result = connection.execute(text(command))
                    print(f"   ✅ Reparación {i}/13 completada")
                except Exception as e:
                    print(f"   ⚠️  Reparación {i}/13: {e}")
            
            trans.commit()
            print("✅ Reparaciones completadas exitosamente.")
            
    except Exception as e:
        print(f"❌ Error durante las reparaciones: {e}")

def option_recreate_tables():
    """
    Opción alternativa: Recrear todas las tablas desde cero
    """
    print("\n🚨 OPCIÓN ALTERNATIVA: Recrear todas las tablas")
    print("⚠️  ADVERTENCIA: Esto borrará todos los datos existentes.")
    
    confirm = input("¿Estás seguro de que quieres recrear las tablas? (escribe 'RECREAR' para confirmar): ")
    if confirm != 'RECREAR':
        print("🛑 Operación cancelada.")
        return
    
    try:
        # Importar las funciones necesarias
        from drop_all_tables import drop_database_tables
        from init_db import create_database_tables
        
        print("🗑️ Eliminando tablas existentes...")
        drop_database_tables()
        
        print("🏗️ Creando tablas nuevas...")
        create_database_tables()
        
        print("✅ Tablas recreadas exitosamente.")
        
    except Exception as e:
        print(f"❌ Error recreando tablas: {e}")

if __name__ == "__main__":
    print("🔧 REPARACIÓN DE BASE DE DATOS")
    print("="*50)
    print("1. Reparar esquema (recomendado)")
    print("2. Recrear todas las tablas (elimina datos)")
    print("3. Solo verificar esquema")
    
    choice = input("\nElige una opción (1-3): ").strip()
    
    if choice == "1":
        fix_database_schema()
    elif choice == "2":
        option_recreate_tables()
    elif choice == "3":
        from check_schema import check_database_schema
        check_database_schema()
    else:
        print("❌ Opción no válida")