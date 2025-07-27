from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from agent.tools import get_agent_tools
from services.email_service import EmailService
from config import config
import json
import logging

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

def generate_response(template_name: str, context: dict) -> str:
    """Función utilitaria para generar respuestas consistentes"""
    templates = {
        "welcome": f"""¡Hola! Soy el asistente virtual de {config.COMPANY_NAME} 👋

Estoy aquí para ayudarte a encontrar el equipo de altura perfecto para tu proyecto y generar una cotización personalizada.

Para empezar, me gustaría conocerte un poco mejor. ¿Podrías contarme:
- ¿Cuál es tu nombre?
- ¿De qué empresa eres?
- ¿En qué tipo de proyecto vas a trabajar?

¡Cuéntame todo lo que consideres relevante! 😊""",
        
        "clarification": """No estoy seguro de entender completamente tu solicitud. ¿Podrías ayudarme proporcionando más detalles sobre:

- ¿Qué altura necesitas alcanzar?
- ¿Qué tipo de trabajo vas a realizar?
- ¿Por cuánto tiempo necesitas el equipo?

Esto me ayudará a recomendarte la mejor opción. 😊""",
        
        "missing_documents": """¡Perfecto! Me alegra que te interesen nuestros equipos. 

Para generar tu cotización oficial necesito algunos datos adicionales:

{missing_items}

Puedes enviarme el RUT como foto del documento o simplemente escribir el número. Para el teléfono y email, solo escríbelos en el mensaje.

¿Con cuál prefieres empezar? 😊""",
        
        "error": "Disculpa, tuve un problema procesando tu solicitud. ¿Podrías intentar de nuevo con más detalles?"
    }
    
    template = templates.get(template_name, templates["error"])
    return template.format(**context) if context else template

def router_node(state: AgentState) -> AgentState:
    """Nodo central de enrutamiento que decide el siguiente paso usando LLM"""
    
    router_prompt = f"""Eres el router central de un asistente de ventas de equipos de altura. Analiza el estado actual de la conversación y decide cuál debe ser el siguiente paso.

ESTADO ACTUAL:
- Etapa: {state.get('conversation_stage', 'unknown')}
- Tiene nombre: {'Sí' if state.get('user_name') else 'No'}
- Tiene empresa: {'Sí' if state.get('company_name') else 'No'}
- Tiene teléfono: {'Sí' if state.get('phone') else 'No'}
- Tiene email: {'Sí' if state.get('email') else 'No'}
- Tiene altura: {'Sí' if state.get('project_details', {}).get('height') else 'No'}
- Tiene duración: {'Sí' if state.get('project_details', {}).get('duration_text') else 'No'}
- Tiene equipos recomendados: {'Sí' if state.get('recommended_equipment') else 'No'}
- Tiene documentos RUT: {'Sí' if state.get('documents', {}).get('rut') else 'No'}
- Cotización generada: {'Sí' if state.get('quotation_data') else 'No'}

ÚLTIMO MENSAJE: {state.get('current_message', '')}

OPCIONES DISPONIBLES:
- consultation: Si necesita más información del proyecto o datos del cliente
- analyze_requirements: Si tiene info básica del proyecto pero no ha analizado equipos
- recommend_equipment: Si necesita recomendar o cambiar equipos
- collect_documents: Si tiene equipos seleccionados pero faltan documentos
- generate_quotation: Si tiene todo listo para cotizar
- send_quotation: Si la cotización está generada pero no enviada
- notify_commercial: Si todo está completo
- END: Si la conversación ha terminado completamente

Responde SOLO con una de las opciones exactas de arriba."""

    try:
        response = llm.invoke([{"role": "user", "content": router_prompt}])
        next_node = response.content.strip().lower()
        
        # Validar que la respuesta sea válida
        valid_nodes = ["consultation", "analyze_requirements", "recommend_equipment", 
                      "collect_documents", "generate_quotation", "send_quotation", 
                      "notify_commercial", "end"]
        
        if next_node not in valid_nodes:
            # Fallback: decidir basado en reglas simples
            if not state.get('project_details', {}).get('height'):
                next_node = "consultation"
            elif not state.get('recommended_equipment'):
                next_node = "analyze_requirements"
            elif not state.get('documents', {}).get('rut'):
                next_node = "collect_documents"
            elif not state.get('quotation_data'):
                next_node = "generate_quotation"
            else:
                next_node = "notify_commercial"
        
        state["next_node"] = next_node.upper() if next_node == "end" else next_node
        
        logger.info(f"Router decidió: {state['next_node']}")
        
    except Exception as e:
        logger.error(f"Error en router_node: {e}")
        # Fallback conservador
        state["next_node"] = "consultation"
    
    return state

def welcome_node(state: AgentState) -> AgentState:
    """Nodo de bienvenida e inicialización"""
    
    state["conversation_stage"] = "gathering_info"
    state["response"] = generate_response("welcome", {})
    state["needs_more_info"] = True
    state["next_node"] = "consultation"
    
    return state

def consultation_node(state: AgentState) -> AgentState:
    """Nodo consultor de necesidades con extracción de datos estructurados"""
    
    system_prompt = f"""Eres un consultor experto en equipos de altura de {config.COMPANY_NAME}. Analiza el mensaje del cliente y extrae información estructurada.

INFORMACIÓN ACTUAL:
- Nombre: {state.get('user_name', 'No proporcionado')}
- Empresa: {state.get('company_name', 'No proporcionada')}
- Teléfono: {state.get('phone', 'No proporcionado')}
- Email: {state.get('email', 'No proporcionado')}
- Detalles del proyecto: {json.dumps(state.get('project_details', {}), ensure_ascii=False)}

MENSAJE DEL CLIENTE: {state['current_message']}

TAREAS:
1. Responde de manera conversacional y profesional
2. Extrae la siguiente información si está disponible en el mensaje:
   - height: altura en metros (solo número)
   - duration_text: duración original como aparece en el mensaje
   - duration_number: número de días/semanas/meses
   - work_type: tipo de trabajo (construcción, mantenimiento, pintura, etc.)
   - user_name: nombre de la persona
   - company_name: nombre de la empresa
   - phone: número de teléfono
   - email: email

FORMATO DE RESPUESTA:
Responde con un JSON que contenga:
{{
    "response": "tu respuesta conversacional aquí",
    "extracted_data": {{
        "height": número o null,
        "duration_text": "texto" o null,
        "duration_number": número o null,
        "work_type": "tipo" o null,
        "user_name": "nombre" o null,
        "company_name": "empresa" o null,
        "phone": "teléfono" o null,
        "email": "email" o null
    }},
    "has_sufficient_info": true/false
}}

Marca has_sufficient_info como true solo si tienes altura, duración, tipo de trabajo y nombre del cliente."""

    try:
        response = llm.invoke([{"role": "user", "content": system_prompt}])
        
        # Intentar parsear JSON del LLM
        try:
            result = json.loads(response.content)
        except:
            # Fallback si el LLM no devuelve JSON válido
            result = {
                "response": "Entiendo tu consulta. ¿Podrías contarme un poco más sobre la altura que necesitas alcanzar y por cuánto tiempo sería el alquiler?",
                "extracted_data": {},
                "has_sufficient_info": False
            }
        
        # Actualizar estado con datos extraídos
        extracted = result.get("extracted_data", {})
        project_details = state.get('project_details', {})
        
        for key, value in extracted.items():
            if value is not None:
                if key in ['height', 'duration_text', 'duration_number', 'work_type']:
                    project_details[key] = value
                else:
                    state[key] = value
        
        state['project_details'] = project_details
        state['response'] = result.get("response", "¿Podrías contarme más detalles sobre tu proyecto?")
        state['needs_more_info'] = not result.get("has_sufficient_info", False)
        
        if not state['needs_more_info']:
            state['conversation_stage'] = "analyzing_requirements"
        
        logger.info(f"Consulta procesada - Info suficiente: {not state['needs_more_info']}")
        
    except Exception as e:
        logger.error(f"Error en consultation_node: {e}")
        state['response'] = generate_response("clarification", {})
        state['needs_more_info'] = True
    
    return state

def analyze_requirements_node(state: AgentState) -> AgentState:
    """Nodo analizador de requerimientos con herramienta inteligente"""
    
    try:
        project_details = state.get('project_details', {})
        
        # Crear descripción del proyecto para la herramienta
        project_description = f"""
        Altura necesaria: {project_details.get('height', 'No especificada')} metros
        Tipo de trabajo: {project_details.get('work_type', 'General')}
        Duración: {project_details.get('duration_text', 'No especificada')}
        """
        
        # Usar herramienta mejorada
        from agent.tools import GetEquipmentTool
        equipment_tool = GetEquipmentTool()
        
        # Llamar con descripción del proyecto
        equipment_data = equipment_tool._run(
            project_description=project_description.strip(),
            max_height=project_details.get('height', 10)
        )
        equipment_list = json.loads(equipment_data)
        
        # Tomar las mejores 3 opciones
        state['recommended_equipment'] = equipment_list[:3] if equipment_list else []
        state['conversation_stage'] = "recommending_equipment"
        
        logger.info(f"Análisis completado - {len(state['recommended_equipment'])} equipos recomendados")
        
    except Exception as e:
        logger.error(f"Error en analyze_requirements_node: {e}")
        state['recommended_equipment'] = []
        state['response'] = "Hubo un problema analizando tu proyecto. ¿Podrías proporcionarme los detalles nuevamente?"
    
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
        state['response'] = generate_response("error", {})
    
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
        missing_text = "\n".join(['• ' + item for item in missing_items])
        state['response'] = generate_response("missing_documents", {"missing_items": missing_text})
    else:
        state['response'] = "¡Excelente! Ya tengo toda la información necesaria. Procediendo a generar tu cotización..."
        state['conversation_stage'] = "ready_for_quotation"
    
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
        state['response'] = generate_response("error", {})
    
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