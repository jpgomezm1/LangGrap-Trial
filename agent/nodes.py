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
    max_tokens=300,  # Reducido para ahorrar tokens
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

def extract_info_advanced(message: str) -> dict:
    """
    Extracción avanzada de información con mejor detección de patrones
    """
    message_lower = message.lower()
    extracted = {
        "user_name": None,
        "company_name": None,
        "phone": None,
        "email": None,
        "project_details": {
            "height": None,
            "duration_text": None,
            "duration_number": None,
            "work_type": None
        }
    }
    
    # Mejorar detección de altura
    height_patterns = [
        r'(\d+)\s*(?:metros?|m\b|mts?)',
        r'(\d+)\s*(?:pisos?|plantas?|niveles?)',
        r'altura.*?(\d+)',
        r'(\d+)\s*(?:de altura|alto)',
        r'hasta.*?(\d+)\s*(?:metros?|m\b)',
        r'(\d+)\s*(?:metros?|m\b).*?(?:altura|alto)'
    ]
    
    for pattern in height_patterns:
        match = re.search(pattern, message_lower)
        if match:
            try:
                height = int(match.group(1))
                # Si menciona pisos/plantas, convertir a metros (aprox 3m por piso)
                if any(word in pattern for word in ['pisos', 'plantas', 'niveles']):
                    height = height * 3
                # Validar altura razonable (entre 1 y 100 metros)
                if 1 <= height <= 100:
                    extracted["project_details"]["height"] = height
                    break
            except:
                continue
    
    # Mejorar detección de duración
    duration_patterns = [
        (r'(\d+)\s*(?:días?|day)', 'días'),
        (r'(\d+)\s*(?:semanas?|week)', 'semanas'),
        (r'(\d+)\s*(?:meses?|month)', 'meses'),
        (r'(\d+)\s*(?:años?|year)', 'años'),
        (r'una?\s*(?:semana|week)', '1 semana'),
        (r'un?\s*(?:mes|month)', '1 mes'),
        (r'varios?\s*(?:días?|day)', 'varios días'),
        (r'algunas?\s*(?:semanas?|week)', 'algunas semanas')
    ]
    
    for pattern, unit in duration_patterns:
        match = re.search(pattern, message_lower)
        if match:
            try:
                if 'varios' in pattern or 'algunas' in pattern:
                    extracted["project_details"]["duration_text"] = unit
                    extracted["project_details"]["duration_number"] = 7  # Default
                else:
                    number = int(match.group(1))
                    extracted["project_details"]["duration_text"] = f"{number} {unit}"
                    extracted["project_details"]["duration_number"] = number
                break
            except:
                continue
    
    # Mejorar detección de tipo de trabajo
    work_types = {
        'construcción': ['construc', 'obra', 'build', 'edificar', 'levantar'],
        'mantenimiento': ['manten', 'repair', 'reparar', 'arreglar', 'revisar'],
        'limpieza': ['limpi', 'clean', 'lavar', 'limpiar'],
        'pintura': ['pintu', 'paint', 'pintar'],
        'instalación': ['instal', 'montar', 'colocar', 'poner'],
        'soldadura': ['sold', 'weld', 'soldar'],
        'electricidad': ['eléctric', 'electric', 'cableado', 'cables'],
        'plomería': ['plomer', 'tubería', 'pipes', 'agua'],
        'techos': ['techo', 'roof', 'cubierta', 'tejado'],
        'fachada': ['fachada', 'facade', 'exterior', 'muro']
    }
    
    for work_type, keywords in work_types.items():
        if any(keyword in message_lower for keyword in keywords):
            extracted["project_details"]["work_type"] = work_type
            break
    
    # Detección de nombres (mejorada)
    name_patterns = [
        r'(?:soy|me llamo|mi nombre es)\s+([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)*)',
        r'([A-ZÁÉÍÓÚ][a-záéíóú]+)\s+(?:de|desde|en)\s+(?:la\s+)?(?:empresa|compañía)',
        r'buenos?\s+días?,?\s+soy\s+([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)*)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, message)
        if match:
            name = match.group(1).strip()
            if len(name.split()) <= 3:  # Máximo 3 palabras para un nombre
                extracted["user_name"] = name
                break
    
    # Detección de empresa (mejorada)
    company_patterns = [
        r'(?:empresa|compañía|constructora|grupo)\s+([A-ZÁÉÍÓÚ][A-Za-záéíóú\s]+)',
        r'([A-ZÁÉÍÓÚ][A-Za-záéíóú\s]+)\s+(?:S\.?A\.?S?|LTDA|SAS|CIA)',
        r'de\s+([A-ZÁÉÍÓÚ][A-Za-záéíóú\s]+?)(?:\s+S\.?A\.?S?|\s+LTDA|\s+SAS|$)',
        r'trabajo\s+para\s+([A-ZÁÉÍÓÚ][A-Za-záéíóú\s]+)'
    ]
    
    for pattern in company_patterns:
        match = re.search(pattern, message)
        if match:
            company = match.group(1).strip()
            if 3 <= len(company) <= 50:  # Longitud razonable para nombre de empresa
                extracted["company_name"] = company
                break
    
    # Emails y teléfonos
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, message)
    if email_match:
        extracted["email"] = email_match.group(0)
    
    phone_pattern = r'(?:\+57\s?)?(?:3\d{2}|[1-8]\d{2})\s?\d{3}\s?\d{4}'
    phone_match = re.search(phone_pattern, message)
    if phone_match:
        extracted["phone"] = phone_match.group(0)
    
    return extracted

def extract_equipment_selection(message: str, equipment_list: list) -> int:
    """Extrae qué equipo seleccionó el usuario del mensaje"""
    message_lower = message.lower()
    
    # Buscar números explícitos
    numbers = re.findall(r'\b(\d+)\b', message)
    for num in numbers:
        index = int(num) - 1  # Convertir a índice base 0
        if 0 <= index < len(equipment_list):
            return index
    
    # Buscar palabras ordinales
    ordinals = {
        'primer': 0, 'primera': 0, 'uno': 0,
        'segundo': 1, 'segunda': 1, 'dos': 1,
        'tercer': 2, 'tercera': 2, 'tres': 2
    }
    
    for word, index in ordinals.items():
        if word in message_lower and index < len(equipment_list):
            return index
    
    # Si menciona características específicas, buscar coincidencia
    for i, equipment in enumerate(equipment_list):
        equipment_name = equipment.get('name', '').lower()
        if any(word in equipment_name for word in message_lower.split() if len(word) > 3):
            return i
    
    return None

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
    Router completamente basado en AI que maneja toda la lógica conversacional.
    """
    print("---ROUTER AI NODE---")
    messages = state['messages']
    
    if not messages:
        state["next_node"] = "consultation"
        logger.info("Router AI: Sin mensajes, comenzando consulta")
        return state
    
    # Si el último mensaje es del asistente, esperar respuesta del usuario
    if len(messages) > 0 and isinstance(messages[-1], AIMessage):
        state["next_node"] = "END"
        logger.info("Router AI: Esperando respuesta del cliente")
        return state
    
    # Casos críticos que requieren acción inmediata (no AI)
    if state.get("document_path") and not state.get("client_info"):
        state["next_node"] = "process_rut"
        logger.info("Router AI: Documento recibido, procesando RUT")
        return state
    
    if state.get("quotation_pdf_path"):
        state["next_node"] = "send_quotation"
        logger.info("Router AI: PDF listo, enviando cotización")
        return state
    
    # USAR AI INTELIGENTE PARA TODA LA LÓGICA CONVERSACIONAL
    try:
        intention = classify_conversation_intelligently(messages[-1].content, state)
        state["next_node"] = intention
        logger.info(f"Router AI: Decisión inteligente - {intention}")
        print(f"🧠 AI decidió: {intention}")
        return state
        
    except Exception as e:
        logger.error(f"Error en Router AI: {e}")
        state["next_node"] = "consultation"
        logger.info("Router AI: Fallback seguro a consultation")
        return state

def classify_conversation_intelligently(message: str, state: AgentState) -> str:
    """
    Clasificador AI avanzado que entiende el contexto completo de la conversación.
    """
    
    # Contexto rico del estado actual
    project_details = state.get('project_details', {})
    has_recommendations = bool(state.get('recommended_equipment'))
    has_client_info = bool(state.get('client_info'))
    conversation_stage = state.get('conversation_stage', 'welcome')
    user_name = state.get('user_name', 'Usuario')
    company_name = state.get('company_name', 'No especificada')
    
    # Información de equipos disponibles
    recommendations_summary = ""
    if has_recommendations:
        equipment_names = [eq.get('name', 'Equipo') for eq in state.get('recommended_equipment', [])]
        recommendations_summary = f"Equipos ya recomendados: {', '.join(equipment_names)}"
    
    # Prompt súper inteligente para Gemini
    classification_prompt = f"""Eres un router inteligente para un chatbot experto en alquiler de equipos de altura. Tu trabajo es decidir el siguiente paso en la conversación basado en el contexto completo.

MENSAJE DEL USUARIO: "{message}"

CONTEXTO COMPLETO DE LA CONVERSACIÓN:
- Usuario: {user_name} de {company_name}
- Etapa actual: {conversation_stage}
- Altura necesaria: {project_details.get('height', 'No especificada')}
- Tipo de trabajo: {project_details.get('work_type', 'No especificado')}
- Duración proyecto: {project_details.get('duration_text', 'No especificada')}
- ¿Ya recomendamos equipos?: {has_recommendations}
- {recommendations_summary}
- ¿Tenemos datos del cliente?: {has_client_info}
- Email: {state.get('email', 'No')}
- Teléfono: {state.get('phone', 'No')}

OPCIONES DE NODOS:
1. "company_info" - Usuario pregunta sobre nuestra empresa, servicios, ubicación, experiencia, horarios, contacto
2. "equipment_details" - Usuario pregunta detalles técnicos, funcionamiento, seguridad, capacitación de equipos específicos
3. "analyze_requirements" - Tenemos info COMPLETA del proyecto (altura + trabajo + duración) pero NO hemos recomendado equipos
4. "collect_documents" - Usuario pide cotización pero nos faltan datos (teléfono, email, RUT)
5. "generate_quotation" - Usuario pide cotización y tenemos TODOS los datos necesarios
6. "consultation" - Necesitamos más info del proyecto, usuario se presenta, o conversación general

REGLAS DE DECISIÓN INTELIGENTE:

🏢 EMPRESA: Si pregunta sobre nosotros/servicios/ubicación/experiencia → "company_info"
Ejemplos: "¿Quiénes son?", "¿Qué servicios ofrecen?", "¿Dónde están ubicados?"

🔧 EQUIPOS: Si pregunta detalles técnicos de equipos ya mencionados → "equipment_details"  
Ejemplos: "¿Cómo funciona el elevador?", "¿Qué capacitación incluye?", "¿Es seguro?"

📋 ANÁLISIS: Si tenemos altura + trabajo + duración pero NO equipos → "analyze_requirements"
Solo usar si: altura ≠ null AND work_type ≠ null AND duration_text ≠ null AND no equipos recomendados

💰 COTIZACIÓN SIN DATOS: Si pide precio pero falta email/teléfono → "collect_documents"
Ejemplos: "Quiero cotización" pero no tenemos contacto completo

💰 COTIZACIÓN COMPLETA: Si pide precio y tenemos todo → "generate_quotation" 
Solo si: equipos recomendados + email + teléfono + datos cliente

🗣️ CONSULTA: Todo lo demás (presentaciones, más info proyecto, conversación general)
Ejemplos: "Soy Juan de...", "Necesito para 20 metros", "Trabajo de limpieza"

ANÁLISIS CONTEXTUAL:
- Si dice "me interesa la opción X" → "equipment_details" (quiere saber más del equipo)
- Si dice "perfecto, procedamos" → "collect_documents" or "generate_quotation" 
- Si da altura en pisos → "consultation" (convertir y confirmar)
- Si menciona presupuesto/precio/cotización → evaluar si tenemos datos completos

RESPONDE SOLO con UNA de estas 6 opciones exactas:
company_info, equipment_details, analyze_requirements, collect_documents, generate_quotation, consultation"""

    try:
        rate_limit_delay()
        
        # Usar configuración optimizada para clasificación
        classification_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.05,  # Muy bajo para máxima consistencia
            max_tokens=20      # Solo necesitamos la clasificación
        )
        
        response = classification_llm.invoke(classification_prompt)
        intention = response.content.strip().lower()
        
        # Limpiar respuesta y validar
        valid_intentions = [
            "company_info", "equipment_details", "analyze_requirements",
            "collect_documents", "generate_quotation", "consultation"
        ]
        
        # Buscar coincidencia exacta o parcial
        for valid_intention in valid_intentions:
            if valid_intention in intention:
                logger.info(f"🧠 AI clasificó: {valid_intention}")
                print(f"🎯 Decisión AI: {valid_intention}")
                return valid_intention
        
        # Si no encuentra una válida, analizar contexto para fallback inteligente
        logger.warning(f"🤔 AI respuesta unclear: '{intention}', analizando contexto...")
        return intelligent_fallback(message, state)
            
    except Exception as e:
        logger.error(f"💥 Error en AI classification: {e}")
        return intelligent_fallback(message, state)

def intelligent_fallback(message: str, state: AgentState) -> str:
    """
    Fallback inteligente basado en contexto cuando AI falla.
    """
    message_lower = message.lower()
    project_details = state.get('project_details', {})
    
    # Análisis contextual inteligente
    
    # 1. Preguntas claramente sobre empresa
    company_signals = ['empresa', 'quienes', 'donde', 'ubicacion', 'servicios', 'experiencia', 'años', 'contacto', 'horarios']
    if any(signal in message_lower for signal in company_signals):
        logger.info("🎯 Fallback: Detectada pregunta empresa")
        return "company_info"
    
    # 2. Info completa de proyecto → analizar
    has_complete_project = (
        project_details.get('height') and 
        project_details.get('work_type') and 
        project_details.get('duration_text')
    )
    
    if has_complete_project and not state.get('recommended_equipment'):
        logger.info("🎯 Fallback: Proyecto completo, analizar requisitos")
        return "analyze_requirements"
    
    # 3. Solicitud de cotización
    quotation_signals = ['cotiza', 'precio', 'costo', 'presupuesto', 'cuanto', 'valor']
    if any(signal in message_lower for signal in quotation_signals):
        if state.get('recommended_equipment'):
            if state.get('email') and state.get('phone'):
                logger.info("🎯 Fallback: Cotización con datos completos")
                return "generate_quotation"
            else:
                logger.info("🎯 Fallback: Cotización sin datos cliente")
                return "collect_documents"
        else:
            logger.info("🎯 Fallback: Cotización sin equipos, más info")
            return "consultation"
    
    # 4. Preguntas sobre equipos ya recomendados
    equipment_signals = ['funciona', 'caracteristicas', 'seguridad', 'capacitacion', 'especificaciones']
    if any(signal in message_lower for signal in equipment_signals) and state.get('recommended_equipment'):
        logger.info("🎯 Fallback: Pregunta sobre equipos")
        return "equipment_details"
    
    # 5. Por defecto: continuar conversación
    logger.info("🎯 Fallback: Conversación general")
    return "consultation"

def classify_user_intention(message: str, state: AgentState) -> str:
    """
    Usa Gemini para clasificar la intención del usuario y decidir el siguiente nodo.
    """
    
    # Contexto del estado actual
    project_details = state.get('project_details', {})
    has_recommendations = bool(state.get('recommended_equipment'))
    has_client_info = bool(state.get('client_info'))
    conversation_stage = state.get('conversation_stage', 'welcome')
    
    # Prompt mejorado y más específico
    classification_prompt = f"""Clasifica la intención del usuario en un chatbot de alquiler de equipos de altura.

MENSAJE DEL USUARIO: "{message}"

CONTEXTO:
- Etapa de conversación: {conversation_stage}
- Proyecto definido: {bool(project_details)}
- Tiene recomendaciones de equipos: {has_recommendations}
- Información del cliente recopilada: {has_client_info}

CLASIFICACIONES POSIBLES:
1. "company_info" - Usuario PREGUNTA sobre nuestra empresa (¿quiénes son?, ¿dónde están?, ¿qué servicios ofrecen?, etc.)
2. "equipment_details" - Usuario pregunta detalles técnicos sobre equipos específicos
3. "collect_documents" - Usuario solicita cotización pero nos falta información del cliente
4. "generate_quotation" - Usuario solicita cotización y ya tenemos toda la información
5. "analyze_requirements" - Tenemos información completa del proyecto pero no hemos recomendado equipos
6. "consultation" - Usuario se presenta, da información del proyecto, o conversación general

REGLAS IMPORTANTES:
- Si el usuario se PRESENTA o da su información personal → "consultation"
- Si el usuario PREGUNTA sobre nosotros/empresa → "company_info"
- Si habla de su proyecto/necesidades → "consultation"
- Si pide cotización explícitamente → "collect_documents" o "generate_quotation"

EJEMPLOS:
- "Soy Juan de Constructora ABC" → consultation
- "¿Quiénes son ustedes?" → company_info
- "Necesito equipos para 15 metros" → consultation
- "Quiero una cotización" → collect_documents

RESPONDE SOLO con una de las 6 clasificaciones exactas."""

    try:
        rate_limit_delay()
        
        classification_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.1,  # Muy bajo para consistencia
            max_tokens=15     # Un poco más para asegurar respuesta completa
        )
        
        response = classification_llm.invoke(classification_prompt)
        intention = response.content.strip().lower()
        
        # Limpiar respuesta (a veces Gemini agrega texto extra)
        valid_intentions = [
            "company_info", "equipment_details", "collect_documents",
            "generate_quotation", "analyze_requirements", "consultation"
        ]
        
        # Buscar si alguna clasificación válida está en la respuesta
        for valid_intention in valid_intentions:
            if valid_intention in intention:
                logger.info(f"AI clasificó: {valid_intention}")
                return valid_intention
        
        # Si no encuentra una válida, default a consultation
        logger.warning(f"Clasificación no reconocida: '{intention}', usando consultation")
        return "consultation"
            
    except Exception as e:
        logger.error(f"Error clasificación AI: {e}")
        return "consultation"

def company_info_node(state: AgentState) -> AgentState:
    """
    Nodo para responder preguntas sobre la empresa
    """
    print("---COMPANY INFO NODE---")
    
    last_message = state.get('current_message', '').lower()
    
    # Información base de la empresa
    company_responses = {
        'ubicación': f"Estamos ubicados en Bogotá, Colombia. Hacemos entregas en toda la ciudad y alrededores.",
        'contacto': f"Puedes contactarnos al {config.COMPANY_PHONE} o por email a {config.COMPANY_EMAIL}",
        'horarios': "Atendemos de lunes a viernes de 7:00 AM a 6:00 PM, y sábados de 8:00 AM a 2:00 PM",
        'experiencia': f"{config.COMPANY_NAME} cuenta con más de 10 años de experiencia en alquiler de equipos de altura",
        'servicios': "Ofrecemos alquiler de andamios, elevadores, escaleras y equipos especializados para trabajo en altura",
        'seguridad': "Todos nuestros equipos cumplen con las normas de seguridad colombianas y vienen con capacitación incluida"
    }
    
    # Detectar qué información específica busca
    response = None
    for keyword, info in company_responses.items():
        if keyword in last_message:
            response = info
            break
    
    if not response:
        # Respuesta general sobre la empresa
        response = f"""¡Claro! Te cuento sobre {config.COMPANY_NAME}:

🏗️ **Somos especialistas en equipos de altura** con más de 10 años de experiencia
📍 **Ubicación**: Bogotá, Colombia (entregas en toda la ciudad)
⏰ **Horarios**: Lunes a viernes 7AM-6PM, sábados 8AM-2PM
📞 **Contacto**: {config.COMPANY_PHONE}
📧 **Email**: {config.COMPANY_EMAIL}

**Nuestros servicios incluyen:**
✅ Alquiler de andamios multidireccionales
✅ Elevadores tijera y articulados  
✅ Escaleras telescópicas y extensibles
✅ Capacitación en seguridad incluida
✅ Entrega y recogida sin costo adicional en Bogotá
✅ Soporte técnico 24/7

¿Te gustaría que te ayude a encontrar el equipo perfecto para tu proyecto? 😊"""

    state['response'] = response
    logger.info("Información de empresa proporcionada")
    return state

def equipment_details_node(state: AgentState) -> AgentState:
    """
    Nodo para proporcionar detalles específicos sobre equipos
    """
    print("---EQUIPMENT DETAILS NODE---")
    
    last_message = state.get('current_message', '').lower()
    selected_equipment = state.get('selected_equipment')
    recommended_equipment = state.get('recommended_equipment', [])
    
    if not selected_equipment and recommended_equipment:
        selected_equipment = recommended_equipment[0]  # Usar el primero por defecto
    
    if not selected_equipment:
        state['response'] = "¿Sobre qué equipo te gustaría conocer más detalles?"
        return state
    
    # Detectar qué tipo de información busca
    detail_type = None
    if any(word in last_message for word in ['funciona', 'opera', 'maneja']):
        detail_type = 'operation'
    elif any(word in last_message for word in ['seguridad', 'riesgo', 'protección']):
        detail_type = 'safety'
    elif any(word in last_message for word in ['especificaciones', 'características', 'técnico']):
        detail_type = 'specs'
    elif any(word in last_message for word in ['entrega', 'instalación', 'montaje']):
        detail_type = 'delivery'
    elif any(word in last_message for word in ['capacitación', 'entrenamiento', 'curso']):
        detail_type = 'training'
    
    equipment_name = selected_equipment.get('name', 'el equipo seleccionado')
    
    if detail_type == 'operation':
        response = f"""🔧 **¿Cómo funciona el {equipment_name}?**

{selected_equipment.get('description', 'Equipo profesional para trabajo en altura')}

**Características de operación:**
- Altura máxima: {selected_equipment.get('max_height', 'N/A')} metros
- Capacidad de carga: {selected_equipment.get('specifications', {}).get('peso_max', 'Según especificaciones')}
- Tipo de tracción: {selected_equipment.get('specifications', {}).get('tipo', 'Manual/Eléctrico')}

**Casos de uso ideales:**
{chr(10).join([f"• {use_case.title()}" for use_case in selected_equipment.get('use_cases', ['Trabajo en altura general'])])}

¿Te gustaría que te explique algún aspecto específico del funcionamiento? 🤔"""
    
    elif detail_type == 'safety':
        response = f"""🛡️ **Seguridad del {equipment_name}**

**Requisitos de seguridad:**
{selected_equipment.get('safety_requirements', 'Cumple con todas las normas colombianas de seguridad')}

**Medidas incluidas:**
✅ Certificación de seguridad vigente
✅ Inspección pre-entrega
✅ Manual de operación segura
✅ Capacitación básica incluida
✅ Soporte técnico durante el alquiler

**Equipos de protección requeridos:**
- Arnés de seguridad certificado
- Casco de protección
- Guantes antideslizantes
- Calzado de seguridad

¿Necesitas que incluyamos equipos de protección personal en tu cotización? 🦺"""
    
    elif detail_type == 'specs':
        specs = selected_equipment.get('specifications', {})
        response = f"""📋 **Especificaciones técnicas - {equipment_name}**

**Dimensiones y capacidades:**
- Altura máxima de trabajo: {selected_equipment.get('max_height', 'N/A')} metros
- Material: {specs.get('material', 'Acero galvanizado/Aluminio')}
- Peso máximo: {specs.get('peso_max', 'Según modelo')}
- Dimensiones base: {specs.get('base', 'Según configuración')}

**Características adicionales:**
{chr(10).join([f"• {key.title()}: {value}" for key, value in specs.items() if key not in ['material', 'peso_max', 'base']])}

¿Necesitas especificaciones más detalladas para tu proyecto? 📐"""
    
    elif detail_type == 'delivery':
        response = f"""🚚 **Entrega e instalación del {equipment_name}**

**Servicio de entrega incluido:**
✅ Entrega gratuita en Bogotá y alrededores
✅ Instalación y configuración básica
✅ Verificación de seguridad en sitio
✅ Capacitación al personal

**Proceso de entrega:**
1️⃣ Coordinamos fecha y hora contigo
2️⃣ Nuestro equipo lleva el equipo al sitio
3️⃣ Realizamos instalación y verificación
4️⃣ Capacitamos a tu personal
5️⃣ Te entregamos documentación

**Tiempos:**
- Entrega: 24-48 horas después de confirmado
- Recogida: Coordinada según tu cronograma

¿Tienes algún requerimiento especial para la entrega? 📅"""
    
    elif detail_type == 'training':
        response = f"""🎓 **Capacitación para el {equipment_name}**

**Capacitación incluida:**
✅ Operación segura del equipo
✅ Procedimientos de emergencia
✅ Inspección diaria básica
✅ Uso correcto de EPP

**Duración:** 2-3 horas según el equipo
**Modalidad:** Presencial en tu obra
**Certificado:** Entregamos constancia de capacitación

**Temas principales:**
- Principios de seguridad en altura
- Operación paso a paso del equipo
- Identificación de riesgos
- Protocolo de emergencias
- Mantenimiento básico

¿Cuántas personas de tu equipo necesitan capacitación? 👥"""
    
    else:
        # Información general del equipo
        response = f"""ℹ️ **Información completa - {equipment_name}**

{selected_equipment.get('description', 'Equipo profesional para trabajo en altura')}

**Resumen:**
- 🏗️ Altura máxima: {selected_equipment.get('max_height', 'N/A')} metros
- 💰 Precio por día: ${selected_equipment.get('daily_price', 0):,.0f}
- 🎯 Ideal para: {', '.join(selected_equipment.get('use_cases', ['trabajo general']))}

**¿Qué te gustaría saber específicamente?**
🔧 Funcionamiento y operación
🛡️ Medidas de seguridad
📋 Especificaciones técnicas
🚚 Entrega e instalación
🎓 Capacitación incluida

¿O prefieres que procedamos con la cotización? 😊"""
    
    state['response'] = response
    logger.info(f"Detalles de equipo proporcionados: {detail_type or 'general'}")
    return state

def consultation_node(state: AgentState) -> AgentState:
    """
    Nodo de consulta mejorado con mejor extracción de información
    """
    print("---CONSULTATION NODE---")
    
    messages = state['messages']
    last_user_message = state.get('current_message', '')
    conversation_stage = state.get('conversation_stage', 'welcome')
    
    # Si es una pregunta sobre cotización sin info completa
    if any(word in last_user_message.lower() for word in ['cotiza', 'precio', 'costo']) and not state.get('project_details', {}).get('height'):
        state['response'] = """¡Perfecto! Con gusto te ayudo con una cotización personalizada. 

Para darte las mejores opciones necesito conocer un poco sobre tu proyecto:

🏗️ **¿A qué altura necesitas trabajar?** (en metros o número de pisos)
🔨 **¿Qué tipo de trabajo vas a realizar?** (construcción, mantenimiento, limpieza, pintura, etc.)
⏰ **¿Por cuánto tiempo necesitas el equipo?** (días, semanas, meses)

Con esta información podré recomendarte el equipo perfecto y darte un precio exacto. 😊"""
        return state
    
    try:
        # Extracción mejorada de información
        extracted = extract_info_advanced(last_user_message)
        
        # Actualizar estado con los datos extraídos
        if extracted.get("user_name"): 
            state["user_name"] = extracted["user_name"]
        if extracted.get("company_name"): 
            state["company_name"] = extracted["company_name"]
        if extracted.get("phone"): 
            state["phone"] = extracted["phone"]
        if extracted.get("email"): 
            state["email"] = extracted["email"]
        
        # Actualizar detalles del proyecto
        if extracted["project_details"]:
            if "project_details" not in state: 
                state["project_details"] = {}
            for key, value in extracted["project_details"].items():
                if value is not None:
                    state["project_details"][key] = value
        
        # Generar respuesta contextual
        project_details = state.get('project_details', {})
        
        # Determinar qué información falta
        missing_info = []
        if not project_details.get('height'):
            missing_info.append("altura de trabajo")
        if not project_details.get('work_type'):
            missing_info.append("tipo de trabajo")
        if not project_details.get('duration_text'):
            missing_info.append("duración del proyecto")
        
        if len(messages) <= 2:  # Primera interacción
            response_text = generate_response("welcome", {})
        elif missing_info:
            if len(missing_info) == 3:
                response_text = "¿Podrías contarme más sobre tu proyecto? Me ayudaría saber a qué altura necesitas trabajar, qué tipo de trabajo vas a realizar y por cuánto tiempo necesitas el equipo. 😊"
            elif 'altura de trabajo' in missing_info:
                response_text = "¿A qué altura necesitas trabajar? Puedes decirme en metros o número de pisos. 📏"
            elif 'tipo de trabajo' in missing_info:
                response_text = "¿Qué tipo de trabajo vas a realizar? Por ejemplo: construcción, mantenimiento, limpieza, pintura, instalaciones, etc. 🔨"
            elif 'duración del proyecto' in missing_info:
                response_text = "¿Por cuánto tiempo necesitas el equipo? (días, semanas o meses) ⏰"
        else:
            # 🎯 AQUÍ ESTÁ LA CLAVE: SI TENEMOS TODA LA INFO, FORZAR EL SIGUIENTE NODO
            height_text = f"{project_details.get('height')}m"
            work_type = project_details.get('work_type', 'trabajo')
            duration = project_details.get('duration_text', 'el tiempo especificado')
            
            response_text = f"""¡Perfecto! Ya tengo toda la información que necesito:

📋 **Resumen de tu proyecto:**
- Altura: {height_text}
- Trabajo: {work_type}
- Duración: {duration}

Ahora voy a buscar las mejores opciones de equipos para tu proyecto. Dame un momento... 🔍"""
            
            # 🚀 FORZAR QUE EL PRÓXIMO NODO SEA ANALYZE_REQUIREMENTS
            state['next_node'] = 'analyze_requirements'
            state['conversation_stage'] = 'analyzing_requirements'
        
        state['response'] = response_text
        logger.info("Consulta mejorada procesada exitosamente")
        
    except Exception as e:
        logger.error(f"Error en consultation_node: {e}")
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