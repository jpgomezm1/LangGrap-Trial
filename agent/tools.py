from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Equipment, Conversation, Quotation
import json

class GetEquipmentTool(BaseTool):
    name = "get_equipment"
    description = "Obtiene información sobre equipos disponibles basado en criterios específicos"
    
    def _run(self, category: str = None, max_height: float = None, use_case: str = None) -> str:
        db = SessionLocal()
        try:
            query = db.query(Equipment).filter(Equipment.available == True)
            
            if category:
                query = query.filter(Equipment.category.ilike(f"%{category}%"))
            
            if max_height:
                query = query.filter(Equipment.max_height >= max_height)
            
            if use_case:
                query = query.filter(Equipment.use_cases.contains([use_case]))
            
            equipment = query.all()
            
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

class SaveConversationTool(BaseTool):
    name = "save_conversation"
    description = "Guarda o actualiza el estado de la conversación en la base de datos"
    
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

class CalculateQuotationTool(BaseTool):
    name = "calculate_quotation"
    description = "Calcula el precio total de una cotización basada en equipos y duración"
    
    def _run(self, equipment_ids: List[int], rental_days: int) -> str:
        db = SessionLocal()
        try:
            total_amount = 0
            equipment_details = []
            
            for eq_id in equipment_ids:
                equipment = db.query(Equipment).filter(Equipment.id == eq_id).first()
                if equipment:
                    # Calcular precio basado en duración
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

class ValidateDocumentTool(BaseTool):
    name = "validate_document"
    description = "Valida que un documento RUT tenga el formato correcto"
    
    def _run(self, document_text: str) -> str:
        # Validación básica de RUT colombiano
        if len(document_text.strip()) < 8:
            return "El RUT debe tener al menos 8 dígitos"
        
        if not document_text.strip().isdigit():
            return "El RUT debe contener solo números"
        
        return "Documento válido"

def get_agent_tools():
    return [
        GetEquipmentTool(),
        SaveConversationTool(),
        CalculateQuotationTool(),
        ValidateDocumentTool()
    ]