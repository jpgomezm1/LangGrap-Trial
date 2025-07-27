# agent/nodes.py

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import AgentState
from agent.tools import get_agent_tools, process_rut_with_gemini, generate_quotation_pdf
from services.email_service import EmailService
from config import config
import json
import logging
import time
import re

logger = logging.getLogger(__name__)

# Inicializar el modelo Gemini con configuración optimizada
llm = ChatGoogleGenerativeAI(
    model=config.MODEL_NAME,
    google_api_key=config.GOOGLE_API_KEY,
    temperature=0.3,  # Reducido para ser más consistente
    max_tokens=300,   # Reducido para ahorrar tokens
)

# Inicializar servicio de email
email_service = EmailService()

def rate_limit_delay():
    """Añade un pequeño delay para evitar exceder la cuota"""
    time.sleep(0.8)  # 800ms delay entre llamadas

def safe_llm_invoke(prompt, max_retries=3):
    """Invoca el LLM de forma segura con manejo de errores y reintentos"""
    for attempt in range(max_retries):
        try:
            rate_limit_delay()  # Delay preventivo
            response = llm.invoke(prompt)
            return response
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait_time = min(60 * (attempt + 1), 300)  # Espera progresiva hasta 5 min
                logger.warning(f"Cuota excedida, esperando {wait_time}s antes del intento {attempt + 1}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Error en LLM (intento {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2)  # Espera 2s antes del siguiente intento
    
    raise Exception("Se agotaron los reintentos para el LLM")

def extract_info_simple(message):
    """Extracción simple de información sin usar LLM"""
    message_lower = message.lower()
    extracted = {
        "user_name": None,
        "company_name": None,
        "phone": None,
        "email": None,
        "rut_text": None,
        "project_details": {
            "height": None,
            "duration_text": None,
            "work_type": None
        }
    }
    
    # Buscar alturas (números seguidos de "metros", "m", "pisos", "plantas")
    height_patterns = [
        r'(\d+)\s*(?:metros?|m\b)',
        r'(\d+)\s*(?:pisos?|plantas?)',
        r'altura.*?(\d+)',
        r'(\d+)\s*(?:de altura|alto)'
    ]
    
    for pattern in height_patterns:
        match = re.search(pattern, message_lower)
        if match:
            try:
                height = int(match.group(1))
                if height > 50:  # Si es muy alto, probablemente sean plantas
                    height = height * 3  # Aproximadamente 3m por planta
                extracted["project_details"]["height"] = height
                break
            except:
                pass
    
    # Buscar duración
    duration_patterns = [
        r'(\d+)\s*(?:días?|day)',
        r'(\d+)\s*(?:semanas?|week)',
        r'(\d+)\s*(?:meses?|month)',
        r'(\d+)\s*(?:años?|year)'
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, message_lower)
        if match:
            extracted["project_details"]["duration_text"] = match.group(0)
            break
    
    # Buscar tipo de trabajo
    if any(word in message_lower for word in ['limpi', 'clean']):
        extracted["project_details"]["work_type"] = "limpieza"
    elif any(word in message_lower for word in ['manten', 'repair']):
        extracted["project_details"]["work_type"] = "mantenimiento"
    elif any(word in message_lower for word in ['construc', 'build']):
        extracted["project_details"]["work_type"] = "construcción"
    elif any(word in message_lower for word in ['pintu', 'paint']):
        extracted["project_details"]["work_type"] = "pintura"
    
    # Buscar emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, message)
    if email_match:
        extracted["email"] = email_match.group(0)
    
    # Buscar teléfonos
    phone_pattern = r'(?:\+57\s?)?(?:3\d{2}|[1-8]\d{2})\s?\d{3}\s?\d{4}'
    phone_match = re.search(phone_pattern, message)
    if phone_match:
        extracted["phone"] = phone_match.group(0)
    
    return extracted

def generate_response(template_name: str, context: dict) -> str:
    """Función utilitaria para generar respuestas consistentes"""
    templates = {
        "welcome": f"""¡Hola! Soy Sebastián, tu asistente de {config.COMPANY_NAME} 👋

Estoy aquí para ayudarte a encontrar el equipo de altura perfecto para tu proyecto.

¿Podrías contarme qué tipo de trabajo necesitas realizar y a qué altura? 😊""",
        
        "clarification": """¿Podrías darme más detalles sobre:
- ¿A qué altura necesitas trabajar?
- ¿Qué tipo de trabajo vas a realizar?
- ¿Por cuánto tiempo lo necesitas?

Esto me ayudará a recomendarte la mejor opción. 😊""",
        
        "missing_documents": """¡Perfecto! Para generar tu cotización necesito:

{missing_items}

¿Con cuál prefieres empezar? 😊""",
        
        "error": "Disculpa, tuve un problema. ¿Podrías darme más detalles sobre tu proyecto?",
        
        "quota_exceeded": "Disculpa, estoy procesando muchas consultas. Dame un momento y vuelve a intentarlo en unos minutos. 😊"
    }
    
    template = templates.get(template_name, templates["error"])
    return template.format(**context) if context else template

def router_node(state: AgentState) -> AgentState:
    """
    Nodo central de enrutamiento optimizado con lógica más simple.
    """
    print("---ROUTER NODE---")
    messages = state['messages']
    
    if not messages:
        state["next_node"] = "consultation"
        logger.info("Router: Sin mensajes, comenzando consulta")
        return state
    
    last_message = messages[-1].content.lower()

    # --- Lógica de enrutamiento explícita y priorizada ---

    # 1. Si acabamos de recibir un documento, debemos procesarlo.
    if state.get("document_path") and not state.get("client_info"):
        state["next_node"] = "process_rut"
        logger.info("Router: Documento recibido, procesando RUT")
        return state
    
    # 2. Si el usuario pide cotización y ya tenemos equipo seleccionado
    if ("cotiza" in last_message or "cotización" in last_message or "precio" in last_message) and state.get('selected_equipment'):
        # Si aún no tenemos info del cliente, la pedimos
        if not state.get('client_info'):
            state["next_node"] = "collect_documents"
            logger.info("Router: Cotización solicitada, recolectando documentos")
        else: # Si ya la tenemos, generamos la cotización
            state["next_node"] = "generate_quotation"
            logger.info("Router: Generando cotización")
        return state

    # 3. Si ya se generó el PDF, lo enviamos.
    if state.get("quotation_pdf_path"):
        state["next_node"] = "send_quotation"
        logger.info("Router: PDF listo, enviando cotización")
        return state

    # 4. Si el último mensaje es del asistente, esperar
    if len(messages) > 0 and isinstance(messages[-1], AIMessage):
        state["next_node"] = "END"
        logger.info("Router: Esperando respuesta del cliente")
        return state

    # 5. Si tenemos suficiente información del proyecto, analizar
    project_details = state.get('project_details', {})
    if project_details.get('height') and project_details.get('work_type'):
        state["next_node"] = "analyze_requirements"
        logger.info("Router: Información completa, analizando requisitos")
        return state

    # 6. Por defecto, seguir en consulta
    state["next_node"] = "consultation"
    logger.info("Router: Continuando consulta")
    return state

def consultation_node(state: AgentState) -> AgentState:
    """
    Gestiona la conversación consultiva con el cliente de forma optimizada.
    """
    print("---CONSULTATION NODE---")
    
    messages = state['messages']
    # Determina si es el primer mensaje real del usuario
    is_first_interaction = len(messages) <= 2
    last_user_message = state.get('current_message', '')

    try:
        # Extraer información usando método simple primero
        extracted = extract_info_simple(last_user_message)
        
        # Actualizar estado con los datos extraídos
        if extracted.get("user_name"): 
            state["user_name"] = extracted["user_name"]
        if extracted.get("company_name"): 
            state["company_name"] = extracted["company_name"]
        if extracted.get("phone"): 
            state["phone"] = extracted["phone"]
        if extracted.get("email"): 
            state["email"] = extracted["email"]
        if extracted.get("rut_text"):
            if "documents" not in state: state["documents"] = {}
            state["documents"]["rut"] = {"text": extracted["rut_text"], "received": True}
        
        if extracted["project_details"]:
            if "project_details" not in state: 
                state["project_details"] = {}
            for key, value in extracted["project_details"].items():
                if value is not None:
                    state["project_details"][key] = value

        # Generar respuesta basada en lo que falta
        project_details = state.get('project_details', {})
        
        if is_first_interaction:
            response_text = generate_response("welcome", {})
        elif not project_details.get('height'):
            response_text = "¿A qué altura necesitas trabajar? (en metros o número de pisos)"
        elif not project_details.get('work_type'):
            response_text = "¿Qué tipo de trabajo vas a realizar? (limpieza, mantenimiento, construcción, etc.)"
        elif not project_details.get('duration_text'):
            response_text = "¿Por cuánto tiempo necesitas el equipo? (días, semanas, meses)"
        else:
            # Si tenemos toda la info, confirmar que buscaremos opciones
            response_text = f"Perfecto, tengo toda la información. Voy a buscar las mejores opciones de equipos para tu trabajo de {project_details.get('work_type')} a {project_details.get('height')}m por {project_details.get('duration_text')}."
        
        state['response'] = response_text
        logger.info(f"Consulta procesada exitosamente")
        
    except Exception as e:
        logger.error(f"Error en consultation_node: {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            state['response'] = generate_response("quota_exceeded", {})
        else:
            state['response'] = generate_response("error", {})
    
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
        state['selected_equipment'] = recommended_equipment[0]  # Seleccionar el primero por defecto
        
        logger.info("Recomendaciones generadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error en recommend_equipment_node: {e}")
        state['response'] = generate_response("error", {})
    
    return state

def collect_documents_node(state: AgentState) -> AgentState:
    """
    Nodo recolector de documentos. Ahora es más simple y solo se activa
    si el router detecta que, tras pedir la cotización, falta algún dato.
    """
    
    # NODO DE RECOLECCIÓN SIMPLIFICADO
    missing_items_text = []
    if not state.get('phone'):
        missing_items_text.append("un número de teléfono de contacto")
    if not state.get('email'):
        missing_items_text.append("un email para enviar la cotización")
    if not state.get('documents', {}).get('rut'):
        missing_items_text.append("el RUT de la empresa (puedes escribir el número o adjuntar el archivo)")

    if missing_items_text:
        missing_str = " y ".join(missing_items_text)
        state['response'] = f"¡Claro que sí! Con gusto preparo tu cotización. Para finalizar, solo necesito que me ayudes con {missing_str}. ¡Gracias!"
    else:
        # Esto es un fallback, en teoría el router no debería llegar aquí si ya todo está completo.
        state['response'] = "¡Perfecto! Ya tengo todo lo necesario. Estoy generando tu cotización ahora mismo..."
        state['next_node'] = "generate_quotation" # Forzamos el siguiente paso
    
    return state

def process_rut_node(state: AgentState) -> AgentState:
    """
    Procesa el archivo RUT (PDF) para extraer la información del cliente.
    """
    print("---PROCESS RUT NODE---")
    file_path = state.get("document_path")
    
    if not file_path:
        state['response'] = "Por favor, para continuar, envíame el archivo PDF de tu RUT."
        return state

    try:
        client_info = process_rut_with_gemini(file_path)
        
        if "error" in client_info:
            state['response'] = f"Tuve un problema al leer el documento. El error fue: {client_info['error']}. ¿Podrías intentar enviarlo de nuevo?"
            return state
        
        # Actualizamos el estado con la información extraída
        state['client_info'] = client_info
        state['company_name'] = client_info.get('company_name')
        state['nit'] = client_info.get('nit')
        state['email'] = client_info.get('email')
        state['document_path'] = None  # Limpiamos la ruta para no procesarlo de nuevo
        
        state['response'] = f"¡Perfecto! He procesado el RUT. Confirmo que la empresa es {client_info.get('company_name', 'N/A')}. Ahora, procederé a generar la cotización."
        
        print(f"Información del RUT procesada: {client_info}")
        logger.info(f"RUT procesado exitosamente para {client_info.get('company_name')}")
        
    except Exception as e:
        print(f"Error al procesar el RUT: {e}")
        logger.error(f"Error al procesar el RUT: {e}")
        state['response'] = "Tuve un problema al leer el documento. ¿Podrías intentar enviarlo de nuevo, por favor?"
    
    return state

def generate_quotation_node(state: AgentState) -> AgentState:
    """
    Genera el PDF de la cotización y lo prepara para el envío.
    """
    print("---GENERATE QUOTATION NODE---")
    
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
        
        # ESTA ES LA CORRECCIÓN CRÍTICA: Generar PDF y devolver la ruta
        pdf_path = generate_quotation_pdf(
            client_info=state.get('client_info', {}),
            recommended_equipment=state['recommended_equipment'],
            quotation_data=quotation,
            project_details=project_details
        )
        
        # Guarda la ruta del PDF de la cotización en el estado
        state['quotation_pdf_path'] = pdf_path
        
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

¡Listo! He generado tu cotización en PDF. Te la enviaré en un momento."""
        
        state['quotation_data'] = quotation
        state['response'] = quotation_message
        state['ready_for_quotation'] = True
        state['conversation_stage'] = "quotation_generated"
        
        logger.info(f"Cotización generada - Total: ${quotation['total_amount']:,.0f}")
        
    except Exception as e:
        logger.error(f"Error generando cotización: {e}")
        state['response'] = "Hubo un error al crear el documento de la cotización. Estoy notificando al equipo para que te ayude."
        
    return state

def send_quotation_node(state: AgentState) -> AgentState:
    """
    Envía la cotización al cliente y notifica al equipo comercial.
    Este nodo ahora también se encarga de enviar el PDF.
    """
    print("---SEND QUOTATION NODE---")
    user_id = state.get('user_id')
    quotation_pdf_path = state.get("quotation_pdf_path")
    
    if not quotation_pdf_path:
        print("❌ Error: No se encontró la ruta del PDF de la cotización en el estado.")
        logger.error("No se encontró la ruta del PDF de la cotización en el estado.")
        state['response'] = "Lo siento, tuve un problema generando el documento de la cotización. Un asesor comercial se pondrá en contacto contigo a la brevedad."
        return state

    # Prepara el mensaje final para el usuario
    final_message = "¡Listo! Aquí tienes tu cotización. Nuestro equipo comercial la revisará y se pondrá en contacto contigo si es necesario. ¡Gracias por confiar en EquiposUp!"
    
    # La responsabilidad de enviar el mensaje y el documento por Telegram
    # se delega al servicio de Telegram para mantener los nodos agnósticos a la plataforma.
    # Guardamos la ruta del PDF y el mensaje en el estado para que el servicio de Telegram los use.
    state['response_type'] = 'document'
    state['document_to_send'] = quotation_pdf_path
    state['final_message'] = final_message
    state['response'] = final_message
    
    print(f"Preparado para enviar cotización en PDF a {user_id}: {quotation_pdf_path}")
    
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
            "stage": state.get('conversation_stage', 'quotation_sent'),
            "quotation_sent": True
        }
        
        save_tool._run(state.get('user_id'), conversation_data)
        logger.info(f"Conversación guardada para usuario {state.get('user_id')}")
        
    except Exception as e:
        logger.error(f"Error guardando conversación: {e}")
    
    state['quotation_sent'] = True
    state['conversation_stage'] = "quotation_sent"
    
    return state

def notify_commercial_node(state: AgentState) -> AgentState:
    """Nodo notificador comercial"""
    
    try:
        logger.info(f"Cotización completada para usuario {state.get('user_id')} - {state.get('company_name')}")
        
        state['commercial_notified'] = True
        state['response'] = f"""¡Perfecto! Tu cotización ha sido procesada exitosamente. 

Nuestro equipo comercial ha sido notificado y se pondrá en contacto contigo en las próximas horas para coordinar todos los detalles del alquiler.

¡Gracias por elegir {config.COMPANY_NAME} para tu proyecto! 🎉

Si tienes alguna pregunta urgente, puedes contactarnos directamente en: {config.COMPANY_DOMAIN}"""
        
    except Exception as e:
        logger.error(f"Error en notify_commercial_node: {e}")
        state['commercial_notified'] = True
        state['response'] = f"¡Cotización completada! Nuestro equipo se pondrá en contacto contigo pronto. ¡Gracias por elegir {config.COMPANY_NAME}! 🚀"
    
    return state