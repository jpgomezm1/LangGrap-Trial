from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Equipment, Conversation, Quotation
import json

class GetEquipmentArgs(BaseModel):
    """Argumentos para la herramienta GetEquipment"""
    project_description: str = Field(description="Descripción completa del proyecto incluyendo altura, tipo de trabajo y duración")
    max_height: Optional[float] = Field(default=None, description="Altura máxima requerida en metros")
    category: Optional[str] = Field(default=None, description="Categoría específica de equipo si se conoce")

class GetEquipmentTool(BaseTool):
    name = "get_equipment"
    description = "Obtiene información sobre equipos disponibles basado en la descripción del proyecto"
    args_schema: Type[BaseModel] = GetEquipmentArgs
    
    def _run(self, project_description: str = "", max_height: float = None, category: str = None) -> str:
        db = SessionLocal()
        try:
            query = db.query(Equipment).filter(Equipment.available == True)
            
            # Análisis inteligente de la descripción del proyecto
            description_lower = project_description.lower()
            
            # Determinar categoría automáticamente si no se proporciona
            if not category:
                if any(word in description_lower for word in ['pintura', 'mantenimiento', 'limpieza']) and (max_height or 0) <= 3:
                    category = "escaleras"
                elif any(word in description_lower for word in ['construcción', 'obra']) and (max_height or 0) <= 8:
                    category = "andamios"
                elif (max_height or 0) > 8:
                    category = "elevadores"
                else:
                    category = "andamios"  # Default
            
            # Filtrar por categoría
            if category:
                query = query.filter(Equipment.category.ilike(f"%{category}%"))
            
            # Filtrar por altura
            if max_height:
                query = query.filter(Equipment.max_height >= max_height)
            
            # Ordenar por relevancia (altura y precio)
            query = query.order_by(Equipment.max_height.asc(), Equipment.daily_price.asc())
            
            equipment = query.limit(5).all()  # Limitar a 5 mejores opciones
            
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
            
            return json.dumps(result, ensure_ascii=False)
        
        finally:
            db.close()

class SaveConversationArgs(BaseModel):
    """Argumentos para guardar conversación"""
    user_id: str = Field(description="ID único del usuario")
    conversation_data: Dict[str, Any] = Field(description="Datos de la conversación a guardar")

class SaveConversationTool(BaseTool):
    name = "save_conversation"
    description = "Guarda o actualiza el estado de la conversación en la base de datos"
    args_schema: Type[BaseModel] = SaveConversationArgs
    
    def _run(self, user_id: str, conversation_data: Dict[str, Any]) -> str:
        db = SessionLocal()
        try:
            # Buscar conversación existente
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            
            if conversation:
                # Actualizar conversación existente
                for key, value in conversation_data.items():
                    if hasattr(conversation, key):
                        setattr(conversation, key, value)
            else:
                # Crear nueva conversación
                conversation = Conversation(user_id=user_id, **conversation_data)
                db.add(conversation)
            
            db.commit()
            return f"Conversación guardada exitosamente para usuario {user_id}"
        
        except Exception as e:
            db.rollback()
            return f"Error guardando conversación: {str(e)}"
        
        finally:
            db.close()

class CalculateQuotationArgs(BaseModel):
    """Argumentos para calcular cotización"""
    equipment_ids: List[int] = Field(description="Lista de IDs de equipos para cotizar")
    rental_days: int = Field(description="Número de días de alquiler")

class CalculateQuotationTool(BaseTool):
    name = "calculate_quotation"
    description = "Calcula el precio total de una cotización basada en equipos y duración"
    args_schema: Type[BaseModel] = CalculateQuotationArgs
    
    def _run(self, equipment_ids: List[int], rental_days: int) -> str:
        db = SessionLocal()
        try:
            total_amount = 0
            equipment_details = []
            
            for eq_id in equipment_ids:
                equipment = db.query(Equipment).filter(Equipment.id == eq_id).first()
                if equipment:
                    # Calcular precio basado en duración con lógica mejorada
                    if rental_days >= 30 and equipment.monthly_price:
                        months = rental_days // 30
                        remaining_days = rental_days % 30
                        price = (months * equipment.monthly_price) + (remaining_days * equipment.daily_price)
                    elif rental_days >= 7 and equipment.weekly_price:
                        weeks = rental_days // 7
                        remaining_days = rental_days % 7
                        price = (weeks * equipment.weekly_price) + (remaining_days * equipment.daily_price)
                    else:
                        price = rental_days * equipment.daily_price
                    
                    total_amount += price
                    
                    equipment_details.append({
                        "id": equipment.id,
                        "name": equipment.name,
                        "daily_price": equipment.daily_price,
                        "calculated_price": price,
                        "rental_days": rental_days
                    })
            
            quotation = {
                "equipment_details": equipment_details,
                "rental_days": rental_days,
                "subtotal": total_amount,
                "tax": total_amount * 0.19,  # IVA Colombia
                "total_amount": total_amount * 1.19
            }
            
            return json.dumps(quotation, ensure_ascii=False)
        
        finally:
            db.close()

class ValidateDocumentArgs(BaseModel):
    """Argumentos para validar documento"""
    document_text: str = Field(description="Texto del documento a validar")

class ValidateDocumentTool(BaseTool):
    name = "validate_document"
    description = "Valida que un documento RUT tenga el formato correcto"
    args_schema: Type[BaseModel] = ValidateDocumentArgs
    
    def _run(self, document_text: str) -> str:
        # Validación básica de RUT colombiano
        clean_text = document_text.strip()
        
        if len(clean_text) < 8:
            return "El RUT debe tener al menos 8 dígitos"
        
        if not clean_text.replace('-', '').isdigit():
            return "El RUT debe contener solo números y guiones"
        
        if len(clean_text) > 15:
            return "El RUT no puede tener más de 15 caracteres"
        
        return "Documento válido"

def get_agent_tools():
    """Retorna lista de herramientas disponibles para el agente"""
    return [
        GetEquipmentTool(),
        SaveConversationTool(),
        CalculateQuotationTool(),
        ValidateDocumentTool()
    ]