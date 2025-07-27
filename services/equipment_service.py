from database.connection import SessionLocal
from database.models import Equipment
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class EquipmentService:
    def __init__(self):
        self.db = SessionLocal()
    
    def get_equipment_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Obtiene equipos por categoría"""
        try:
            equipment = self.db.query(Equipment).filter(
                Equipment.category.ilike(f"%{category}%"),
                Equipment.available == True
            ).all()
            
            result = []
            for eq in equipment:
                result.append({
                    "id": eq.id,
                    "name": eq.name,
                    "category": eq.category,
                    "description": eq.description,
                    "max_height": eq.max_height,
                    "daily_price": eq.daily_price,
                    "weekly_price": eq.weekly_price,
                    "monthly_price": eq.monthly_price,
                    "specifications": eq.specifications,
                    "use_cases": eq.use_cases,
                    "safety_requirements": eq.safety_requirements
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo equipos: {e}")
            return []
    
    def seed_sample_equipment(self):
        """Agrega equipos de ejemplo a la base de datos"""
        try:
            # Verificar si ya hay equipos
            existing_count = self.db.query(Equipment).count()
            if existing_count > 0:
                logger.info("Ya existen equipos en la base de datos")
                return
            
            sample_equipment = [
                {
                    "name": "Andamio Multidireccional 6m",
                    "category": "andamios",
                    "description": "Andamio multidireccional ideal para trabajos de construcción y mantenimiento hasta 6 metros de altura",
                    "max_height": 6.0,
                    "daily_price": 45000,
                    "weekly_price": 270000,
                    "monthly_price": 900000,
                    "specifications": {"material": "Acero galvanizado", "peso_max": "300kg", "base": "1.5x1.5m"},
                    "use_cases": ["construcción", "mantenimiento", "pintura"],
                    "safety_requirements": "Uso obligatorio de arnés de seguridad",
                    "available": True
                },
                {
                    "name": "Elevador Tijera 10m",
                    "category": "elevadores",
                    "description": "Plataforma elevadora tijera eléctrica para trabajos en altura hasta 10 metros",
                    "max_height": 10.0,
                    "daily_price": 180000,
                    "weekly_price": 1080000,
                    "monthly_price": 3600000,
                    "specifications": {"tipo": "Eléctrico", "capacidad": "230kg", "plataforma": "2.3x1.1m"},
                    "use_cases": ["mantenimiento", "instalaciones", "limpieza"],
                    "safety_requirements": "Certificación de operador requerida",
                    "available": True
                },
                {
                    "name": "Escalera Telescópica 4m",
                    "category": "escaleras",
                    "description": "Escalera telescópica de aluminio extensible hasta 4 metros",
                    "max_height": 4.0,
                    "daily_price": 25000,
                    "weekly_price": 150000,
                    "monthly_price": 500000,
                    "specifications": {"material": "Aluminio", "peso": "12kg", "peldaños": "13"},
                    "use_cases": ["mantenimiento", "limpieza", "instalaciones menores"],
                    "safety_requirements": "Uso en superficie firme y nivelada",
                    "available": True
                }
            ]
            
            for eq_data in sample_equipment:
                equipment = Equipment(**eq_data)
                self.db.add(equipment)
            
            self.db.commit()
            logger.info("Equipos de ejemplo agregados exitosamente")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error agregando equipos de ejemplo: {e}")
    
    def __del__(self):
        self.db.close()