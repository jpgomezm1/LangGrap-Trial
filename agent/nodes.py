# agent/nodes.py

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
    """
    Nodo central de enrutamiento. Ahora es más inteligente para evitar atascos.
    """
    conversation_history = "\n".join(
        [f"{'Cliente' if isinstance(msg, HumanMessage) else 'Asistente'}: {msg.content}" for msg in state.get('messages', [])[-6:]]
    )

    # REGLA DE ORO MEJORADA: Solo termina si la última respuesta es del asistente Y el nuevo mensaje del cliente es muy corto o no aporta nada.
    last_message_is_from_assistant = len(state['messages']) > 0 and isinstance(state['messages'][-1], AIMessage)

    if last_message_is_from_assistant:
        state["next_node"] = "END"
        logger.info("Router (Sebastián) decidió: END (esperando respuesta del cliente)")
        return state

    router_prompt = f"""Eres "Sebastián", el asistente de ventas experto de EquiposUp. Tu trabajo es decidir el siguiente paso en la conversación.

HISTORIAL RECIENTE:
{conversation_history}

ESTADO ACTUAL DE LA CONVERSACIÓN:
- Cliente: {state.get('user_name', 'No')}
- Empresa: {state.get('company_name', 'No')}
- Contacto (teléfono, email): {'Sí' if state.get('phone') and state.get('email') else 'No'}
- Detalles del proyecto (altura, duración, tipo): {'Sí' if all(k in state.get('project_details', {}) for k in ['height', 'duration_text', 'work_type']) else 'No'}
- RUT Recibido: {'Sí' if state.get('documents', {}).get('rut') else 'No'}

OPCIONES (siguiente nodo):
- consultation: ¡Úsalo siempre que haya un nuevo mensaje del cliente! Este nodo procesará lo que dijo.
- analyze_requirements: Si ya tienes los 3 detalles del proyecto.
- collect_documents: Si el cliente ya vio las recomendaciones y quiere cotizar, pero faltan datos de contacto o el RUT.
- generate_quotation: Si tienes absolutamente todo.

¿Cuál es el siguiente paso? Responde SOLO con el nombre del nodo.
"""
    try:
        response = llm.invoke(router_prompt)
        next_node = response.content.strip().lower().split()[0].replace("`", "").replace("'", "").replace('"', '')
        state["next_node"] = next_node
        logger.info(f"Router (Sebastián) decidió: {state['next_node']}")
    except Exception as e:
        logger.error(f"Error en router_node: {e}", exc_info=True)
        state["next_node"] = "END"
        state["response"] = "¡Uy! Tuve un percance técnico. ¿Podríamos intentarlo de nuevo?"
    
    return state

def consultation_node(state: AgentState) -> AgentState:
    """
    Gestiona la conversación consultiva con el cliente con un prompt dinámico y consciente del historial.
    """
    print("---CONSULTATION NODE---")
    
    # Construir el historial de la conversación
    conversation_history = ""
    messages = state.get('messages', [])
    for msg in messages:
        role = "Cliente" if isinstance(msg, HumanMessage) else "Asistente"
        conversation_history += f"{role}: {msg.content}\n"
    
    last_user_message = state.get('current_message', '')
    is_first_message = len(messages) <= 1
    
    # --- PROMPT DINÁMICO MEJORADO ---
    if is_first_message:
        system_prompt = f"""
Eres "Sebastián", un asistente de ventas experto y amigable de EquiposUp. Es el primer contacto con este cliente.

**Instrucciones:**
1. **Presentación Natural:** Preséntate de manera cálida y profesional
2. **Pregunta Abierta:** Pregunta en qué puedes ayudar al cliente
3. **Tono Conversacional:** Habla como un humano, no como un robot
4. **Guía Sutil:** Si es apropiado, menciona que necesitarás algunos detalles del proyecto

Último mensaje del cliente: "{last_user_message}"

Responde de manera natural y amigable.
"""
    else:
        system_prompt = f"""
Eres "Sebastián", asistente de ventas de EquiposUp. Mantienes una conversación fluida con un cliente.

**Historial de la conversación:**
{conversation_history}

**Estado actual:**
- Cliente: {state.get('user_name', 'No identificado')}
- Empresa: {state.get('company_name', 'No especificada')}
- Proyecto: {state.get('project_details', {})}

**Instrucciones:**
1. **Continuidad:** Usa el contexto del historial para responder coherentemente
2. **Extracción:** Identifica y confirma cualquier información nueva (nombre, empresa, altura, duración, tipo de trabajo, teléfono, email, RUT)
3. **Progreso Natural:** Si tienes suficiente información para el siguiente paso, guía naturalmente hacia allá
4. **Una Pregunta:** Haz máximo una pregunta clara por respuesta
5. **Evita Repetición:** No repitas saludos o información ya confirmada

Último mensaje del cliente: "{last_user_message}"

Genera una respuesta que extraiga información relevante y mantenga la conversación fluida.
"""

    try:
        # Llamada al LLM con el prompt dinámico
        response = llm.invoke(system_prompt)
        
        # Extraer información del mensaje actual
        extraction_prompt = f"""
Analiza este mensaje del cliente y extrae información relevante en formato JSON:
"{last_user_message}"

JSON a extraer:
{{
  "user_name": "nombre" o null,
  "company_name": "empresa" o null,
  "phone": "telefono" o null,
  "email": "email" o null,
  "rut_text": "numero de RUT" o null,
  "project_details": {{
    "height": numero o null,
    "duration_text": "duracion" o null,
    "work_type": "tipo de trabajo" o null
  }}
}}
"""
        
        # Extraer datos
        try:
            extraction_response = llm.invoke(extraction_prompt)
            extracted = json.loads(extraction_response.content.strip().replace("```json", "").replace("```", ""))
            
            # Actualizar estado con los datos extraídos
            if extracted.get("user_name"): state["user_name"] = extracted["user_name"]
            if extracted.get("company_name"): state["company_name"] = extracted["company_name"]
            if extracted.get("phone"): state["phone"] = extracted["phone"]
            if extracted.get("email"): state["email"] = extracted["email"]
            if extracted.get("rut_text"):
                if "documents" not in state: state["documents"] = {}
                state["documents"]["rut"] = {"text": extracted["rut_text"], "received": True}
            
            if "project_details" in extracted and extracted["project_details"]:
                if "project_details" not in state: state["project_details"] = {}
                for key, value in extracted["project_details"].items():
                    if value is not None:
                        state["project_details"][key] = value
                        
        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
        
        state['response'] = response.content
        logger.info(f"Consulta procesada. Respuesta: {state['response'][:50]}...")
        
    except Exception as e:
        logger.error(f"Error en consultation_node: {e}", exc_info=True)
        state['response'] = "Parece que no entendí muy bien. ¿Podrías explicármelo de otra forma, por favor?"
    
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
    """
    Nodo recolector de documentos. Ahora es más simple y solo se activa
    si el router detecta que, tras pedir la cotización, falta algún dato.
    La extracción se delega al `consultation_node`.
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
    file_path = state.get("document_path") # Asumimos que la ruta del PDF se guarda en el estado

    if not file_path:
        # Si no hay documento, pide al usuario que lo envíe
        message = "¡Entendido! Para generar la cotización, necesito que por favor me envíes el RUT de la empresa en formato PDF."
        state['response'] = message
        return state

    try:
        # Llama a la herramienta para procesar el PDF
        from agent.tools import process_rut_with_gemini
        client_info = process_rut_with_gemini(file_path) # Esta herramienta usa Gemini Vision
        
        # Actualiza el estado con la información extraída
        state['client_info'] = client_info
        print(f"Información del RUT procesada: {client_info}")

        message = f"¡Perfecto! He procesado el RUT. Veo que la empresa es {client_info.get('company_name')}. Ahora, procederé a generar la cotización."
        state['response'] = message
        
    except Exception as e:
        print(f"Error al procesar el RUT: {e}")
        logger.error(f"Error al procesar el RUT: {e}")
        message = "Tuve un problema al leer el documento. ¿Podrías intentar enviarlo de nuevo, por favor?"
        state['response'] = message
    
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
        
        from agent.tools import CalculateQuotationTool, generate_quotation_pdf
        quotation_tool = CalculateQuotationTool()
        
        quotation_data = quotation_tool._run(equipment_ids, rental_days)
        quotation = json.loads(quotation_data)
        
        # Generar PDF de la cotización
        quotation_path = generate_quotation_pdf(
            client_info=state.get('client_info', {}),
            recommended_equipment=state['recommended_equipment'],
            quotation_data=quotation,
            project_details=project_details
        )
        
        # Guarda la ruta del PDF de la cotización en el estado
        state['quotation_pdf_path'] = quotation_path
        
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
        print("Error: No se encontró la ruta del PDF de la cotización en el estado.")
        logger.error("No se encontró la ruta del PDF de la cotización en el estado.")
        state['response'] = "Hubo un problema generando el documento. Nuestro equipo comercial se pondrá en contacto contigo."
        return state

    # Prepara el mensaje final para el usuario
    final_message = "Te he enviado la cotización a tu correo y también adjunta aquí en el chat. Si tienes alguna otra pregunta, no dudes en consultarme."
    
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
        state['response'] = """¡Perfecto! Tu cotización ha sido procesada exitosamente. 

Nuestro equipo comercial ha sido notificado y se pondrá en contacto contigo en las próximas horas para coordinar todos los detalles del alquiler.

¡Gracias por elegir EquiposUp para tu proyecto! 🎉

Si tienes alguna pregunta urgente, puedes contactarnos directamente en nuestro sitio web: https://equiposup.com/"""
        
    except Exception as e:
        logger.error(f"Error en notify_commercial_node: {e}")
        state['commercial_notified'] = True
        state['response'] = "¡Cotización completada! Nuestro equipo se pondrá en contacto contigo pronto. ¡Gracias por elegir EquiposUp! 🚀"
    
    return state