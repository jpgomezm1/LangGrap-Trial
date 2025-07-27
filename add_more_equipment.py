# add_more_equipment.py

import os
from dotenv import load_dotenv
from database.connection import SessionLocal
from database.models import Equipment
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_comprehensive_equipment():
    """
    Agrega una lista completa de 15+ equipos de altura variados a la base de datos
    """
    db = SessionLocal()
    
    try:
        print("🏗️ Agregando equipos adicionales a la base de datos...")
        
        # Lista completa de equipos
        new_equipment = [
            # ESCALERAS (1-6 metros)
            {
                "name": "Escalera Telescópica 3m",
                "category": "escaleras",
                "description": "Escalera telescópica de aluminio liviana, ideal para trabajos domésticos y mantenimiento básico",
                "max_height": 3.0,
                "daily_price": 15000,
                "weekly_price": 90000,
                "monthly_price": 300000,
                "specifications": {"material": "Aluminio", "peso": "8kg", "peldaños": "10", "capacidad": "150kg"},
                "use_cases": ["mantenimiento doméstico", "limpieza básica", "instalaciones menores", "pintura residencial"],
                "safety_requirements": "Uso en superficie firme, ángulo 75°, una persona máximo",
                "available": True
            },
            {
                "name": "Escalera Extensible 5m",
                "category": "escaleras",
                "description": "Escalera extensible profesional de aluminio con sistema de seguridad antideslizante",
                "max_height": 5.0,
                "daily_price": 28000,
                "weekly_price": 168000,
                "monthly_price": 560000,
                "specifications": {"material": "Aluminio reforzado", "peso": "15kg", "peldaños": "16", "capacidad": "200kg"},
                "use_cases": ["mantenimiento comercial", "limpieza de fachadas", "instalaciones eléctricas", "trabajos de pintura"],
                "safety_requirements": "Certificación de estabilidad, arnés recomendado arriba de 3m",
                "available": True
            },
            
            # ANDAMIOS (4-12 metros)
            {
                "name": "Andamio Tubular 4m",
                "category": "andamios",
                "description": "Andamio tubular básico galvanizado, fácil montaje, ideal para construcción residencial",
                "max_height": 4.0,
                "daily_price": 35000,
                "weekly_price": 210000,
                "monthly_price": 700000,
                "specifications": {"material": "Acero galvanizado", "peso_max": "250kg", "base": "1.2x1.2m", "torres": "2"},
                "use_cases": ["construcción residencial", "reparaciones", "pintura exterior", "mantenimiento básico"],
                "safety_requirements": "Base firme y nivelada, arnés obligatorio",
                "available": True
            },
            {
                "name": "Andamio Multidireccional 8m",
                "category": "andamios",
                "description": "Andamio multidireccional profesional con plataformas de trabajo amplias y barandillas de seguridad",
                "max_height": 8.0,
                "daily_price": 65000,
                "weekly_price": 390000,
                "monthly_price": 1300000,
                "specifications": {"material": "Acero galvanizado", "peso_max": "400kg", "base": "1.8x1.8m", "torres": "4"},
                "use_cases": ["construcción comercial", "mantenimiento industrial", "fachadas", "instalaciones grandes"],
                "safety_requirements": "Montaje por personal certificado, arnés obligatorio, inspección diaria",
                "available": True
            },
            {
                "name": "Andamio Torre Móvil 10m",
                "category": "andamios",
                "description": "Torre móvil con ruedas, altura ajustable, perfecta para trabajos que requieren movilidad",
                "max_height": 10.0,
                "daily_price": 85000,
                "weekly_price": 510000,
                "monthly_price": 1700000,
                "specifications": {"material": "Aleación ligera", "peso_max": "300kg", "base": "1.5x1.5m", "ruedas": "4 con freno"},
                "use_cases": ["mantenimiento de naves", "limpieza industrial", "instalaciones técnicas", "reparaciones rápidas"],
                "safety_requirements": "Frenos activados durante uso, superficie plana, personal capacitado",
                "available": True
            },
            {
                "name": "Andamio Colgante 12m",
                "category": "andamios",
                "description": "Sistema de andamio colgante para trabajos en fachadas y edificios altos",
                "max_height": 12.0,
                "daily_price": 120000,
                "weekly_price": 720000,
                "monthly_price": 2400000,
                "specifications": {"material": "Acero certificado", "peso_max": "500kg", "longitud": "6m", "ancho": "0.8m"},
                "use_cases": ["limpieza de fachadas", "mantenimiento de edificios", "trabajos de altura comercial", "reparaciones exteriores"],
                "safety_requirements": "Certificación estructural del edificio, operarios certificados, doble línea de vida",
                "available": True
            },
            
            # ELEVADORES (6-20 metros)
            {
                "name": "Elevador Tijera Eléctrico 6m",
                "category": "elevadores",
                "description": "Plataforma elevadora tijera compacta, ideal para trabajos en interiores y espacios reducidos",
                "max_height": 6.0,
                "daily_price": 95000,
                "weekly_price": 570000,
                "monthly_price": 1900000,
                "specifications": {"tipo": "Eléctrico", "capacidad": "230kg", "plataforma": "1.8x0.9m", "peso": "1200kg"},
                "use_cases": ["mantenimiento interior", "instalaciones en bodegas", "limpieza de techos", "trabajos eléctricos"],
                "safety_requirements": "Operador certificado, superficie firme, área despejada",
                "available": True
            },
            {
                "name": "Elevador Tijera Diésel 12m",
                "category": "elevadores",
                "description": "Elevador tijera todo terreno para exteriores, motor diésel, alta capacidad de carga",
                "max_height": 12.0,
                "daily_price": 220000,
                "weekly_price": 1320000,
                "monthly_price": 4400000,
                "specifications": {"tipo": "Diésel", "capacidad": "450kg", "plataforma": "2.4x1.2m", "peso": "3500kg"},
                "use_cases": ["construcción exterior", "mantenimiento industrial", "montaje de estructuras", "trabajos pesados"],
                "safety_requirements": "Licencia de operación, inspección previa del terreno, equipo de protección completo",
                "available": True
            },
            {
                "name": "Elevador Articulado 14m",
                "category": "elevadores",
                "description": "Brazo articulado que permite acceso a lugares difíciles, ideal para trabajos de precisión",
                "max_height": 14.0,
                "daily_price": 280000,
                "weekly_price": 1680000,
                "monthly_price": 5600000,
                "specifications": {"tipo": "Híbrido", "capacidad": "230kg", "alcance_horizontal": "7m", "rotación": "360°"},
                "use_cases": ["podas de árboles", "mantenimiento de señalización", "trabajos sobre obstáculos", "instalaciones complejas"],
                "safety_requirements": "Operador especializado, análisis de riesgos, coordenadas de emergencia",
                "available": True
            },
            {
                "name": "Elevador Telescópico 16m",
                "category": "elevadores",
                "description": "Brazo telescópico recto para alcance máximo en altura, estabilidad superior",
                "max_height": 16.0,
                "daily_price": 350000,
                "weekly_price": 2100000,
                "monthly_price": 7000000,
                "specifications": {"tipo": "Diésel 4x4", "capacidad": "300kg", "alcance_horizontal": "9m", "estabilizadores": "4"},
                "use_cases": ["mantenimiento de antenas", "limpieza de edificios altos", "montaje industrial", "rescate en altura"],
                "safety_requirements": "Certificación avanzada, plan de rescate, comunicación permanente",
                "available": True
            },
            {
                "name": "Elevador Oruga 18m",
                "category": "elevadores",
                "description": "Elevador sobre orugas para terrenos difíciles, máxima estabilidad y tracción",
                "max_height": 18.0,
                "daily_price": 420000,
                "weekly_price": 2520000,
                "monthly_price": 8400000,
                "specifications": {"tipo": "Oruga diésel", "capacidad": "400kg", "ancho_oruga": "230mm", "pendiente_max": "30°"},
                "use_cases": ["trabajos en pendientes", "terrenos irregulares", "proyectos forestales", "mantenimiento en montaña"],
                "safety_requirements": "Operador experto en terrenos, equipos de comunicación, rescate especializado",
                "available": True
            },
            {
                "name": "Elevador Araña 20m",
                "category": "elevadores",
                "description": "Elevador tipo araña ultraliviano, acceso por espacios estrechos, máxima versatilidad",
                "max_height": 20.0,
                "daily_price": 480000,
                "weekly_price": 2880000,
                "monthly_price": 9600000,
                "specifications": {"tipo": "Eléctrico/Batería", "capacidad": "200kg", "ancho_min": "0.8m", "peso": "1800kg"},
                "use_cases": ["interiores de edificios", "espacios confinados", "mantenimiento de museos", "trabajos de precisión"],
                "safety_requirements": "Acceso restringido, personal especializado, protocolos de espacios confinados",
                "available": True
            },
            
            # EQUIPOS ESPECIALIZADOS
            {
                "name": "Plataforma Suspendida 2 Puntos",
                "category": "equipos_especializados",
                "description": "Plataforma suspendida por cables para trabajos en fachadas de edificios altos",
                "max_height": 100.0,  # Limitado por el edificio
                "daily_price": 150000,
                "weekly_price": 900000,
                "monthly_price": 3000000,
                "specifications": {"capacidad": "300kg", "longitud": "6m", "velocidad": "6m/min", "cables": "Acero galvanizado"},
                "use_cases": ["limpieza de ventanas", "mantenimiento de fachadas", "pintura exterior", "instalación de vidrios"],
                "safety_requirements": "Anclajes certificados, doble cable de seguridad, operarios especializados",
                "available": True
            },
            {
                "name": "Escalera de Bomberos 25m",
                "category": "equipos_especializados",
                "description": "Escalera extensible tipo bomberos para emergencias y trabajos de rescate",
                "max_height": 25.0,
                "daily_price": 200000,
                "weekly_price": 1200000,
                "monthly_price": 4000000,
                "specifications": {"material": "Aleación especial", "peso": "80kg", "capacidad": "200kg", "secciones": "3"},
                "use_cases": ["rescate", "acceso de emergencia", "mantenimiento de torres", "trabajos especiales"],
                "safety_requirements": "Personal certificado en rescate, protocolos de emergencia, comunicación constante",
                "available": True
            },
            {
                "name": "Grúa Canasta 30m",
                "category": "equipos_especializados",
                "description": "Grúa con canasta para personas, alcance extremo, para proyectos industriales grandes",
                "max_height": 30.0,
                "daily_price": 650000,
                "weekly_price": 3900000,
                "monthly_price": 13000000,
                "specifications": {"capacidad": "500kg", "alcance": "25m", "canasta": "2x1.2m", "estabilizadores": "4 hidráulicos"},
                "use_cases": ["mantenimiento industrial", "montaje de estructuras", "trabajos en torres", "proyectos especiales"],
                "safety_requirements": "Operador con licencia especial, ingeniería de soporte, permisos municipales",
                "available": True
            },
            {
                "name": "Andamio Europeo Certificado 15m",
                "category": "andamios",
                "description": "Sistema de andamio europeo con certificación internacional, máxima seguridad",
                "max_height": 15.0,
                "daily_price": 180000,
                "weekly_price": 1080000,
                "monthly_price": 3600000,
                "specifications": {"certificacion": "EN-12811", "capacidad": "600kg", "modular": "Si", "galvanizado": "Hot-dip"},
                "use_cases": ["proyectos internacionales", "construcción premium", "obras públicas", "edificios corporativos"],
                "safety_requirements": "Montaje certificado, inspecciones programadas, documentación completa",
                "available": True
            }
        ]
        
        # Verificar cuántos equipos ya existen
        existing_count = db.query(Equipment).count()
        print(f"📊 Equipos existentes en la BD: {existing_count}")
        
        added_count = 0
        skipped_count = 0
        
        for eq_data in new_equipment:
            # Verificar si ya existe un equipo con el mismo nombre
            existing = db.query(Equipment).filter(Equipment.name == eq_data["name"]).first()
            
            if not existing:
                equipment = Equipment(**eq_data)
                db.add(equipment)
                added_count += 1
                print(f"  ✅ Agregado: {eq_data['name']} (Altura: {eq_data['max_height']}m)")
            else:
                skipped_count += 1
                print(f"  ⏭️ Ya existe: {eq_data['name']}")
        
        # Confirmar cambios
        db.commit()
        
        # Resumen final
        final_count = db.query(Equipment).count()
        print(f"\n📈 RESUMEN:")
        print(f"  • Equipos agregados: {added_count}")
        print(f"  • Equipos omitidos (ya existían): {skipped_count}")
        print(f"  • Total en la BD: {final_count}")
        
        # Mostrar distribución por categoría
        print(f"\n📊 DISTRIBUCIÓN POR CATEGORÍA:")
        categories = db.execute("""
            SELECT category, COUNT(*) as count, 
                   MIN(max_height) as min_height, 
                   MAX(max_height) as max_height
            FROM equipment 
            WHERE available = true 
            GROUP BY category 
            ORDER BY min_height
        """).fetchall()
        
        for cat in categories:
            print(f"  • {cat[0]}: {cat[1]} equipos (Altura: {cat[2]}-{cat[3]}m)")
            
        print(f"\n✅ ¡Proceso completado exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error agregando equipos: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

def verify_equipment_database():
    """Verifica el estado actual de la base de datos de equipos"""
    db = SessionLocal()
    
    try:
        print("\n🔍 VERIFICACIÓN DE LA BASE DE DATOS:")
        
        # Contar total
        total = db.query(Equipment).count()
        available = db.query(Equipment).filter(Equipment.available == True).count()
        
        print(f"📊 Total de equipos: {total}")
        print(f"📊 Equipos disponibles: {available}")
        
        # Equipos por rango de altura
        ranges = [
            ("1-5m (Escaleras)", 1, 5),
            ("6-10m (Andamios/Elevadores)", 6, 10),
            ("11-15m (Elevadores)", 11, 15),
            ("16-25m (Especializados)", 16, 25),
            ("25m+ (Industriales)", 25, 100)
        ]
        
        print(f"\n📏 EQUIPOS POR RANGO DE ALTURA:")
        for range_name, min_h, max_h in ranges:
            count = db.query(Equipment).filter(
                Equipment.max_height >= min_h,
                Equipment.max_height <= max_h,
                Equipment.available == True
            ).count()
            print(f"  • {range_name}: {count} equipos")
            
        # Mostrar algunos ejemplos
        print(f"\n🔧 EJEMPLOS DE EQUIPOS DISPONIBLES:")
        sample_equipment = db.query(Equipment).filter(Equipment.available == True).limit(5).all()
        for eq in sample_equipment:
            print(f"  • {eq.name} ({eq.category}) - {eq.max_height}m - ${eq.daily_price:,}/día")
            
    except Exception as e:
        print(f"❌ Error verificando BD: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("🏗️ SCRIPT DE EQUIPOS ADICIONALES - EquiposUp")
    print("=" * 60)
    
    # Verificar estado actual
    verify_equipment_database()
    
    # Preguntar si proceder
    choice = input(f"\n¿Deseas agregar los equipos adicionales? (s/n): ").lower()
    
    if choice == 's':
        success = add_comprehensive_equipment()
        
        if success:
            print(f"\n🎉 ¡Equipos agregados exitosamente!")
            print(f"🚀 Ahora puedes reiniciar el bot y probar con diferentes alturas:")
            print(f"   • 'Necesito escaleras para 4 metros'")
            print(f"   • 'Limpieza de ventanas a 12 metros'") 
            print(f"   • 'Mantenimiento industrial a 18 metros'")
            
            # Verificar estado final
            verify_equipment_database()
        else:
            print(f"❌ Hubo problemas agregando los equipos.")
    else:
        print(f"🛑 Operación cancelada por el usuario.")