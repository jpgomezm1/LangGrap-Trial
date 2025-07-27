from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Equipment, Conversation, Quotation
import json
import os
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from datetime import datetime

# Configura la API de Gemini (asumiendo que ya tienes la key en tus variables de entorno)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

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

def process_rut_with_gemini(pdf_path: str) -> dict:
    """
    Extrae información de un archivo RUT en formato PDF utilizando Gemini Vision.

    Args:
        pdf_path: La ruta local al archivo PDF del RUT.

    Returns:
        Un diccionario con la información extraída (ej. company_name, nit).
    """
    print(f"🛠️ Procesando RUT desde: {pdf_path}")
    
    try:
        # Configuración del modelo Gemini Vision
        model = genai.GenerativeModel('gemini-1.5-pro-latest')

        # Abrir el PDF
        doc = fitz.open(pdf_path)
        
        image_parts = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            image_parts.append(img)

        # Prompt para guiar al modelo en la extracción de datos
        prompt_parts = [
            "Analiza la siguiente imagen de un RUT (Registro Único Tributario) de Colombia.",
            "Extrae la siguiente información en formato JSON estricto:",
            "- Razon Social (clave: 'company_name')",
            "- NIT (Número de Identificación Tributaria) (clave: 'nit')",
            "- Direccion Principal (clave: 'address')",
            "- Correo Electronico de Notificacion (clave: 'email')",
            "- Responsabilidades Tributarias (clave: 'responsibilities'), debe ser una lista de strings.",
            "Si un campo no se encuentra, su valor debe ser null.",
            *image_parts, # Añade las imágenes al prompt
        ]

        # Llamada al modelo
        response = model.generate_content(prompt_parts)
        
        # Limpiar y parsear la respuesta
        # Gemini a veces devuelve el JSON dentro de un bloque de código markdown
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        client_info = json.loads(clean_response)
        
        print(f"✅ Información del RUT extraída: {client_info}")
        return client_info

    except Exception as e:
        print(f"❌ Error al procesar el RUT con Gemini: {e}")
        return {"error": str(e)}

def generate_quotation_pdf(client_info: dict, recommended_equipment: list, quotation_data: dict = None, project_details: dict = None, quotation_id: str = None) -> str:
    """
    Genera un archivo PDF para la cotización.

    Args:
        client_info: Diccionario con la información del cliente (extraída del RUT).
        recommended_equipment: Lista de diccionarios con los equipos recomendados.
        quotation_data: Datos de la cotización calculada.
        project_details: Detalles del proyecto.
        quotation_id: Un identificador único para la cotización.

    Returns:
        La ruta al archivo PDF generado.
    """
    if not quotation_id:
        quotation_id = f"COT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    file_path = f"cotizacion_{quotation_id}.pdf"
    print(f"📄 Creando cotización en PDF: {file_path}")

    try:
        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter

        # --- Cabecera ---
        # Asumiendo que tienes un logo en la misma carpeta
        if os.path.exists("logo.png"):
            c.drawImage("logo.png", 50, height - 100, width=150, preserveAspectRatio=True)
        
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(width - 50, height - 70, "COTIZACIÓN")
        c.setFont("Helvetica", 12)
        c.drawRightString(width - 50, height - 90, f"Nro: {quotation_id}")
        c.drawRightString(width - 50, height - 110, f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")

        # --- Información del Cliente ---
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 150, "Cliente:")
        c.setFont("Helvetica", 11)
        text = c.beginText(50, height - 170)
        text.textLine(f"Razón Social: {client_info.get('company_name', 'N/A')}")
        text.textLine(f"NIT: {client_info.get('nit', 'N/A')}")
        text.textLine(f"Dirección: {client_info.get('address', 'N/A')}")
        text.textLine(f"Email: {client_info.get('email', 'N/A')}")
        c.drawText(text)

        # --- Información del Proyecto ---
        if project_details:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, height - 230, "Detalles del Proyecto:")
            c.setFont("Helvetica", 11)
            text = c.beginText(50, height - 250)
            text.textLine(f"Altura requerida: {project_details.get('height', 'N/A')} metros")
            text.textLine(f"Tipo de trabajo: {project_details.get('work_type', 'N/A')}")
            text.textLine(f"Duración: {project_details.get('duration_text', 'N/A')}")
            c.drawText(text)
            table_start_y = height - 320
        else:
            table_start_y = height - 250

        # --- Tabla de Equipos ---
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, table_start_y, "Detalle de Equipos Cotizados")
        
        y_position = table_start_y - 30
        c.setFont("Helvetica-Bold", 10)
        c.drawString(55, y_position, "Equipo")
        c.drawString(300, y_position, "Precio Unitario (Día)")
        c.drawString(450, y_position, "Total")
        c.line(50, y_position - 5, width - 50, y_position - 5)
        
        c.setFont("Helvetica", 10)
        y_position -= 20
        
        # Usar datos de quotation_data si están disponibles, sino usar recommended_equipment
        if quotation_data and 'equipment_details' in quotation_data:
            equipment_list = quotation_data['equipment_details']
            total_cotizacion = quotation_data.get('total_amount', 0)
            subtotal = quotation_data.get('subtotal', 0)
            tax = quotation_data.get('tax', 0)
        else:
            equipment_list = recommended_equipment
            total_cotizacion = 0
            for item in equipment_list:
                days = item.get('rental_days', item.get('days', 1))
                price_per_day = item.get('daily_price', item.get('price_per_day', 0))
                total_cotizacion += price_per_day * days
            subtotal = total_cotizacion
            tax = total_cotizacion * 0.19
            total_cotizacion = subtotal + tax

        for item in equipment_list:
            name = item.get('name', 'Equipo no especificado')
            price_per_day = item.get('daily_price', item.get('price_per_day', 0))
            total_item = item.get('calculated_price', price_per_day * item.get('rental_days', item.get('days', 1)))
            
            c.drawString(55, y_position, name)
            c.drawString(300, y_position, f"${price_per_day:,.0f}")
            c.drawString(450, y_position, f"${total_item:,.0f}")
            y_position -= 15

        # --- Totales ---
        c.line(50, y_position, width - 50, y_position)
        y_position -= 20
        
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 150, y_position, "Subtotal:")
        c.drawRightString(width - 50, y_position, f"${subtotal:,.0f}")
        y_position -= 15
        
        c.drawRightString(width - 150, y_position, "IVA (19%):")
        c.drawRightString(width - 50, y_position, f"${tax:,.0f}")
        y_position -= 15
        
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(width - 150, y_position, "Total Cotización:")
        c.drawRightString(width - 50, y_position, f"${total_cotizacion:,.0f}")
        
        # --- Condiciones ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y_position - 40, "Condiciones:")
        c.setFont("Helvetica", 9)
        conditions_text = c.beginText(50, y_position - 55)
        conditions_text.textLine("• Precios válidos por 15 días")
        conditions_text.textLine("• Incluye entrega y recogida en Bogotá")
        conditions_text.textLine("• Capacitación básica incluida")
        conditions_text.textLine("• Soporte técnico 24/7")
        conditions_text.textLine("• Precios sujetos a disponibilidad")
        c.drawText(conditions_text)
        
        # --- Pie de página ---
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(50, 50, "Cotización válida por 15 días. Precios no incluyen IVA.")
        c.drawRightString(width - 50, 50, "EquiposUp - Equipos de Altura")

        c.save()
        print(f"✅ Cotización guardada en: {file_path}")
        return file_path
    
    except Exception as e:
        print(f"❌ Error generando el PDF de la cotización: {e}")
        return None

def get_agent_tools():
    """Retorna lista de herramientas disponibles para el agente"""
    return [
        GetEquipmentTool(),
        SaveConversationTool(),
        CalculateQuotationTool(),
        ValidateDocumentTool()
    ]