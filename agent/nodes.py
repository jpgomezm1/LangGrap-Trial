from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from agent.tools import get_agent_tools
from services.email_service import EmailService
from config import config
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

# Inicializar el modelo Gemini
llm = ChatGoogleGenerativeAI(
    model=config.MODEL_NAME,
    google_api_key=config.GOOGLE_API_KEY,
    temperature=config.TEMPERATURE,
    max_tokens=config.MAX_TOKENS
)

# Inicializar servicio de email
email_service = EmailService()

def welcome_node(state: AgentState) -> AgentState:
    """Nodo de bienvenida e inicialización"""
    
    welcome_message = f"""¡Hola! Soy el asistente virtual de {config.COMPANY_NAME} 👋

Estoy aquí para ayudarte a encontrar el equipo de altura perfecto para tu proyecto y generar una cotización personalizada.

Para empezar, me gustaría conocerte un poco mejor. ¿Podrías contarme:
- ¿Cuál es tu nombre?
- ¿De qué empresa eres?
- ¿En qué tipo de proyecto vas a trabajar?

¡Cuéntame todo lo que consideres relevante! 😊"""
    
    # Actualizar estado
    state["conversation_stage"] = "gathering_info"
    state["response"] = welcome_message
    state["needs_more_info"] = True
    
    return state

def consultation_node(state: AgentState) -> AgentState:
    """Nodo consultor de necesidades"""
    
    system_prompt = f"""Eres un consultor experto en equipos de altura de {config.COMPANY_NAME}. Tu objetivo es entender completamente las necesidades del cliente de manera natural y conversacional.

Información actual del cliente:
- Nombre: {state.get('user_name', 'No proporcionado')}
- Empresa: {state.get('company_name', 'No proporcionada')}
- Detalles del proyecto: {json.dumps(state.get('project_details', {}), ensure_ascii=False)}

INSTRUCCIONES:
1. Haz preguntas abiertas y naturales, como si fueras un consultor humano experto
2. Enfócate en entender: tipo de trabajo, altura necesaria, duración del alquiler, ubicación, experiencia previa
3. Identifica el nivel de experiencia del cliente para recomendar equipos apropiados
4. Si el cliente ya proporcionó información, no la vuelvas a preguntar
5. Una vez que tengas suficiente información para hacer una recomendación, indica que procederás con las recomendaciones

Mensaje del cliente: {state['current_message']}

Responde de manera conversacional y profesional en español."""
    
    try:
        response = llm.invoke([{"role": "system", "content": system_prompt}, {"role": "user", "content": state['current_message']}])
        
        # Extraer información del mensaje del cliente
        project_details = state.get('project_details', {})
        
        # Extracción básica de información
        message_lower = state['current_message'].lower()
        
        # Extraer altura
        import re
        height_patterns = [
            r'(\d+)\s*metros?',
            r'(\d+)\s*m\b',
            r'altura.*?(\d+)',
            r'(\d+).*?altura'
        ]
        
        for pattern in height_patterns:
            height_match = re.search(pattern, message_lower)
            if height_match:
                try:
                    height = int(height_match.group(1))
                    if 1 <= height <= 50:  # Rango razonable
                        project_details['height'] = height
                        break
                except ValueError:
                    continue
        
        # Extraer duración
        duration_patterns = [
            r'(\d+)\s*días?',
            r'(\d+)\s*semanas?',
            r'(\d+)\s*meses?',
            r'por\s*(\d+)'
        ]
        
        for pattern in duration_patterns:
            duration_match = re.search(pattern, message_lower)
            if duration_match:
                project_details['duration_text'] = duration_match.group(0)
                project_details['duration_number'] = int(duration_match.group(1))
                break
        
        # Extraer tipo de trabajo
        work_types = ['construcción', 'mantenimiento', 'pintura', 'limpieza', 'instalación', 'reparación']
        for work_type in work_types:
            if work_type in message_lower:
                project_details['work_type'] = work_type
                break
        
        # Determinar si tenemos suficiente información
        has_sufficient_info = (
            'height' in project_details and 
            ('duration_text' in project_details or 'duration_number' in project_details) and
            state.get('user_name') and
            ('work_type' in project_details or any(word in message_lower for word in ['proyecto', 'trabajo', 'obra', 'construcción']))
        )
        
        state['project_details'] = project_details
        state['response'] = response.content
        state['needs_more_info'] = not has_sufficient_info
        
        if has_sufficient_info:
            state['conversation_stage'] = "analyzing_requirements"
        
        logger.info(f"Consulta procesada - Info suficiente: {has_sufficient_info}")
        
    except Exception as e:
        logger.error(f"Error en consultation_node: {e}")
        state['response'] = "Entiendo tu consulta. ¿Podrías contarme un poco más sobre la altura que necesitas alcanzar y por cuánto tiempo sería el alquiler?"
    
    return state

def analyze_requirements_node(state: AgentState) -> AgentState:
    """Nodo analizador de requerimientos"""
    
    try:
        project_details = state.get('project_details', {})
        height = project_details.get('height', 5)  # Default 5m
        
        # Determinar categoría de equipo necesario
        if height <= 3:
            category = "escaleras"
        elif height <= 8:
            category = "andamios"
        elif height <= 15:
            category = "elevadores"
        else:
            category = "equipos_especializados"
        
        # Buscar equipos apropiados
        from agent.tools import GetEquipmentTool
        equipment_tool = GetEquipmentTool()
        
        equipment_data = equipment_tool._run(category=category, max_height=height)
        equipment_list = json.loads(equipment_data)
        
        # Tomar las mejores 3 opciones
        state['recommended_equipment'] = equipment_list[:3] if equipment_list else []
        state['conversation_stage'] = "recommending_equipment"
        
        logger.info(f"Análisis completado - {len(state['recommended_equipment'])} equipos recomendados")
        
    except Exception as e:
        logger.error(f"Error en analyze_requirements_node: {e}")
        state['recommended_equipment'] = []
    
    return state

def recommend_equipment_node(state: AgentState) -> AgentState:
    """Nodo recomendador de equipos"""
    
    try:
        recommended_equipment = state.get('recommended_equipment', [])
        project_details = state.get('project_details', {})
        
        if not recommended_equipment:
            state['response'] = """Lo siento, no encontré equipos específicos para tu proyecto en este momento. 
            
Pero no te preocupes, nuestro equipo comercial puede ayudarte a encontrar la solución perfecta. 
¿Te gustaría que un especialista se ponga en contacto contigo?"""
            return state
        
        # Generar recomendaciones
        recommendations_text = f"""📋 **Recomendaciones para tu proyecto:**

Basándome en tus necesidades (altura: {project_details.get('height', 'N/A')}m), estas son mis recomendaciones:

"""
        
        for i, eq in enumerate(recommended_equipment, 1):
            recommendations_text += f"""**Opción {i}: {eq['name']}**
🎯 Altura máxima: {eq['max_height']}m
💰 Precio: ${eq['daily_price']:,.0f} por día
📝 Descripción: {eq['description']}
✅ Ideal para: {', '.join(eq.get('use_cases', ['uso general']))}

"""
        
        recommendations_text += """¿Cuál de estas opciones te parece más interesante? ¿Tienes alguna pregunta específica sobre algún equipo?

También puedo ayudarte con la cotización si alguna te convence. 😊"""
        
        state['response'] = recommendations_text
        state['conversation_stage'] = "equipment_selected"
        
        logger.info("Recomendaciones generadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error en recommend_equipment_node: {e}")
        state['response'] = "Hubo un problema generando las recomendaciones. ¿Podrías contarme de nuevo sobre tu proyecto?"
    
    return state

def collect_documents_node(state: AgentState) -> AgentState:
    """Nodo recolector de documentos"""
    
    documents = state.get('documents', {})
    has_rut = 'rut' in documents
    has_phone = state.get('phone') is not None
    has_email = state.get('email') is not None
    
    missing_items = []
    if not has_rut:
        missing_items.append("📄 RUT de tu empresa")
    if not has_phone:
        missing_items.append("📱 Número de teléfono")
    if not has_email:
        missing_items.append("📧 Email de contacto")
    
    if missing_items:
        message = f"""¡Perfecto! Me alegra que te interesen nuestros equipos. 

Para generar tu cotización oficial necesito algunos datos adicionales:

{chr(10).join(['• ' + item for item in missing_items])}

Puedes enviarme el RUT como foto del documento o simplemente escribir el número. Para el teléfono y email, solo escríbelos en el mensaje.

¿Con cuál prefieres empezar? 😊"""
    else:
        message = "¡Excelente! Ya tengo toda la información necesaria. Procediendo a generar tu cotización..."
        state['conversation_stage'] = "ready_for_quotation"
    
    state['response'] = message
    return state

def generate_quotation_node(state: AgentState) -> AgentState:
    """Nodo generador de cotización"""
    
    try:
        recommended_equipment = state.get('recommended_equipment', [])
        project_details = state.get('project_details', {})
        
        if not recommended_equipment:
            state['response'] = "No puedo generar la cotización sin equipos seleccionados. ¿Podrías elegir un equipo de las opciones anteriores?"
            return state
        
        # Calcular duración en días
        duration_number = project_details.get('duration_number', 7)
        duration_text = project_details.get('duration_text', '7 días')
        
        rental_days = duration_number
        if 'semana' in duration_text:
            rental_days = duration_number * 7
        elif 'mes' in duration_text:
            rental_days = duration_number * 30
        
        # Calcular cotización
        equipment_ids = [eq['id'] for eq in recommended_equipment]
        
        from agent.tools import CalculateQuotationTool
        quotation_tool = CalculateQuotationTool()
        
        quotation_data = quotation_tool._run(equipment_ids, rental_days)
        quotation = json.loads(quotation_data)
        
        # Generar mensaje de cotización
        quotation_message = f"""🎉 **Cotización Generada - {config.COMPANY_NAME}**

👤 **Cliente:** {state.get('user_name', 'N/A')}
🏢 **Empresa:** {state.get('company_name', 'N/A')}
📞 **Teléfono:** {state.get('phone', 'N/A')}
📧 **Email:** {state.get('email', 'N/A')}

📋 **Detalle de Equipos:**
"""
        
        for eq in quotation['equipment_details']:
            quotation_message += f"""
**{eq['name']}**
- Duración: {eq['rental_days']} días
- Precio por día: ${eq['daily_price']:,.0f}
- Subtotal: ${eq['calculated_price']:,.0f}
"""
        
        quotation_message += f"""
💰 **Resumen Financiero:**
- Subtotal: ${quotation['subtotal']:,.0f}
- IVA (19%): ${quotation['tax']:,.0f}
- **TOTAL: ${quotation['total_amount']:,.0f}**

📝 **Condiciones:**
✅ Precios válidos por 15 días
✅ Incluye entrega y recogida en Bogotá
✅ Capacitación básica incluida
✅ Soporte técnico 24/7

¡Excelente elección! Un miembro de nuestro equipo comercial se pondrá en contacto contigo pronto para coordinar los detalles. 

¿Tienes alguna pregunta sobre esta cotización? 🚀"""
        
        state['quotation_data'] = quotation
        state['response'] = quotation_message
        state['ready_for_quotation'] = True
        state['conversation_stage'] = "quotation_generated"
        
        logger.info(f"Cotización generada - Total: ${quotation['total_amount']:,.0f}")
        
    except Exception as e:
        logger.error(f"Error generando cotización: {e}")
        state['response'] = "Hubo un problema generando la cotización. Nuestro equipo se pondrá en contacto contigo para resolverlo."
    
    return state

def send_quotation_node(state: AgentState) -> AgentState:
    """Nodo enviador de cotización"""
    
    state['quotation_sent'] = True
    state['conversation_stage'] = "quotation_sent"
    
    # Guardar en base de datos
    try:
        from agent.tools import SaveConversationTool
        save_tool = SaveConversationTool()
        
        conversation_data = {
            "user_name": state.get('user_name'),
            "company_name": state.get('company_name'),
            "phone": state.get('phone'),
            "email": state.get('email'),
            "project_details": state.get('project_details'),
            "recommended_equipment": state.get('recommended_equipment'),
            "stage": state['conversation_stage'],
            "quotation_sent": True
        }
        
        save_tool._run(state['user_id'], conversation_data)
        logger.info(f"Conversación guardada para usuario {state['user_id']}")
        
    except Exception as e:
        logger.error(f"Error guardando conversación: {e}")
    
    return state

def notify_commercial_node(state: AgentState) -> AgentState:
    """Nodo notificador comercial"""
    
    try:
        # Por ahora solo logueamos que debería enviarse la notificación
        logger.info(f"Cotización completada para usuario {state.get('user_id')} - {state.get('company_name')}")
        
        state['commercial_notified'] = True
        state['response'] = """¡Perfecto! Tu cotización ha sido procesada exitosamente. 

Nuestro equipo comercial ha sido notificado y se pondrá en contacto contigo en las próximas horas para coordinar todos los detalles del alquiler.

¡Gracias por elegir EquiposUp para tu proyecto! 🎉

Si tienes alguna pregunta urgente, puedes contactarnos directamente en nuestro sitio web: https://equiposup.com/"""
        
    except Exception as e:
        logger.error(f"Error en notify_commercial_node: {e}")
        state['commercial_notified'] = True
        state['response'] = "¡Cotización completada! Nuestro equipo se pondrá en contacto contigo pronto. ¡Gracias por elegir EquiposUp! 🚀"
    
    return state