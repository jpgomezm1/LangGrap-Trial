import logging
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from database.connection import SessionLocal
from database.models import Conversation
import json

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.active_conversations = {}  # Cache en memoria de conversaciones activas
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start"""
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name or "Usuario"
        
        # Inicializar estado
        initial_state = AgentState(
            user_id=user_id,
            user_name=user_name,
            company_name=None,
            phone=None,
            email=None,
            conversation_stage="welcome",
            project_details={},
            recommended_equipment=[],
            quotation_data=None,
            documents={},
            messages=[],
            needs_more_info=True,
            ready_for_quotation=False,
            quotation_sent=False,
            commercial_notified=False,
            current_message="",
            response=""
        )
        
        # Guardar en cache
        self.active_conversations[user_id] = initial_state
        
        welcome_message = """¡Bienvenido a EquiposUp! 🏗️

Soy tu asistente virtual especializado en equipos de altura. Estoy aquí para ayudarte a encontrar la solución perfecta para tu proyecto y generar una cotización personalizada.

Para comenzar, simplemente escríbeme contándome sobre tu proyecto. ¡Empecemos! 😊"""
        
        await update.message.reply_text(welcome_message)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Maneja mensajes de texto"""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        
        try:
            # Obtener o crear estado de conversación
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            # Actualizar mensaje actual
            state["current_message"] = message_text
            state["messages"].append(HumanMessage(content=message_text))
            
            # Extraer información del usuario si está disponible
            await self._extract_user_info(state, message_text)
            
            # Verificar si es la primera vez después del welcome
            if state.get("conversation_stage") == "welcome":
                state["conversation_stage"] = "gathering_info"
            
            # Ejecutar el grafo del agente con manejo de recursión
            try:
                result = agent_graph.invoke(state, config={"recursion_limit": 10})
            except Exception as graph_error:
                logger.error(f"Error en grafo: {graph_error}")
                # Fallback manual basado en el stage actual
                result = await self._handle_fallback_response(state, message_text)
            
            # Actualizar cache
            self.active_conversations[user_id] = result
            
            # Enviar respuesta
            response_text = result.get("response", "Lo siento, no pude procesar tu mensaje.")
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await update.message.reply_text(
                "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?"
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Maneja documentos enviados por el usuario"""
        user_id = str(update.effective_user.id)
        
        try:
            # Obtener estado de conversación
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            # Procesar documento
            document = update.message.document
            document_name = document.file_name or "documento"
            
            # Guardar información del documento
            documents = state.get("documents", {})
            
            if "rut" in document_name.lower() or "nit" in document_name.lower():
                documents["rut"] = {
                    "file_name": document_name,
                    "file_id": document.file_id,
                    "received": True
                }
                response_text = "✅ ¡Perfecto! He recibido tu RUT. "
            else:
                documents["other"] = {
                    "file_name": document_name,
                    "file_id": document.file_id,
                    "received": True
                }
                response_text = "✅ Documento recibido. "
            
            state["documents"] = documents
            state["current_message"] = f"Documento enviado: {document_name}"
            
            # Verificar si tenemos todos los documentos necesarios
            has_rut = "rut" in documents
            has_phone = state.get("phone") is not None
            has_email = state.get("email") is not None
            
            if has_rut and has_phone and has_email:
                response_text += "¡Tengo toda la información necesaria! Generando tu cotización..."
                state["conversation_stage"] = "ready_for_quotation"
            else:
                missing = []
                if not has_rut:
                    missing.append("RUT")
                if not has_phone:
                    missing.append("teléfono")
                if not has_email:
                    missing.append("email")
                
                response_text += f"Aún necesito: {', '.join(missing)}"
            
            # Ejecutar grafo si está listo
            if state["conversation_stage"] == "ready_for_quotation":
                try:
                    result = agent_graph.invoke(state, config={"recursion_limit": 10})
                    self.active_conversations[user_id] = result
                    response_text = result.get("response", response_text)
                except Exception as graph_error:
                    logger.error(f"Error en grafo con documento: {graph_error}")
                    result = await self._handle_fallback_response(state, state["current_message"])
                    self.active_conversations[user_id] = result
                    response_text = result.get("response", response_text)
            else:
                self.active_conversations[user_id] = state
            
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando documento: {e}")
            await update.message.reply_text(
                "Hubo un problema procesando tu documento. ¿Podrías intentar enviarlo de nuevo?"
            )
    
    async def _get_or_create_conversation_state(self, user_id: str, user) -> AgentState:
        """Obtiene o crea el estado de conversación"""
        
        # Intentar obtener del cache
        if user_id in self.active_conversations:
            return self.active_conversations[user_id]
        
        # Intentar obtener de la base de datos
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            
            if conversation:
                # Restaurar estado desde BD
                state = AgentState(
                    user_id=user_id,
                    user_name=conversation.user_name or user.first_name,
                    company_name=conversation.company_name,
                    phone=conversation.phone,
                    email=conversation.email,
                    conversation_stage=conversation.stage,
                    project_details=conversation.project_details or {},
                    recommended_equipment=conversation.recommended_equipment or [],
                    quotation_data=None,
                    documents=conversation.documents or {},
                    messages=[],
                    needs_more_info=conversation.stage in ["welcome", "gathering_info", "consultation"],
                    ready_for_quotation=conversation.quotation_sent,
                    quotation_sent=conversation.quotation_sent,
                    commercial_notified=conversation.commercial_notified,
                    current_message="",
                    response=""
                )
            else:
                # Crear nuevo estado
                state = AgentState(
                    user_id=user_id,
                    user_name=user.first_name or "Usuario",
                    company_name=None,
                    phone=None,
                    email=None,
                    conversation_stage="welcome",
                    project_details={},
                    recommended_equipment=[],
                    quotation_data=None,
                    documents={},
                    messages=[],
                    needs_more_info=True,
                    ready_for_quotation=False,
                    quotation_sent=False,
                    commercial_notified=False,
                    current_message="",
                    response=""
                )
            
            self.active_conversations[user_id] = state
            return state
            
        finally:
            db.close()
    
    async def _extract_user_info(self, state: AgentState, message: str):
        """Extrae información del usuario del mensaje"""
        message_lower = message.lower()
        
        # Extraer teléfono
        import re
        phone_pattern = r'(\+?57\s?)?[3][0-9]{9}'
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            state["phone"] = phone_match.group(0)
        
        # Extraer email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            state["email"] = email_match.group(0)
        
        # Extraer nombre si dice "soy" o "me llamo"
        if "soy" in message_lower or "me llamo" in message_lower:
            # Buscar el nombre después de estas palabras
            name_pattern = r'(?:soy|me llamo)\s+([A-Za-z\s]+)'
            name_match = re.search(name_pattern, message_lower)
            if name_match:
                potential_name = name_match.group(1).strip()
                if len(potential_name) > 1 and len(potential_name) < 50:
                    state["user_name"] = potential_name.title()
        
        # Extraer empresa si dice "de" o "trabajo en"
        if "empresa" in message_lower or "trabajo en" in message_lower or "de la empresa" in message_lower:
            company_patterns = [
                r'empresa\s+([A-Za-z\s&.-]+)',
                r'trabajo en\s+([A-Za-z\s&.-]+)',
                r'de la empresa\s+([A-Za-z\s&.-]+)'
            ]
            for pattern in company_patterns:
                company_match = re.search(pattern, message_lower)
                if company_match:
                    potential_company = company_match.group(1).strip()
                    if len(potential_company) > 1 and len(potential_company) < 100:
                        state["company_name"] = potential_company.title()
                        break
    
    async def _handle_fallback_response(self, state: AgentState, message_text: str) -> AgentState:
        """Manejo manual cuando el grafo falla"""
        stage = state.get("conversation_stage", "welcome")
        
        if stage in ["welcome", "gathering_info"]:
            # Ejecutar consultation_node directamente
            from agent.nodes import consultation_node
            return consultation_node(state)
        
        elif stage == "analyzing_requirements":
            # Ejecutar analyze_requirements_node directamente
            from agent.nodes import analyze_requirements_node
            return analyze_requirements_node(state)
        
        elif stage in ["recommending_equipment", "equipment_selected"]:
            # Ejecutar recommend_equipment_node directamente
            from agent.nodes import recommend_equipment_node
            return recommend_equipment_node(state)
        
        elif stage == "collecting_documents":
            # Ejecutar collect_documents_node directamente
            from agent.nodes import collect_documents_node
            return collect_documents_node(state)
        
        elif stage == "ready_for_quotation":
            # Ejecutar generate_quotation_node directamente
            from agent.nodes import generate_quotation_node
            return generate_quotation_node(state)
        
        else:
            # Respuesta genérica
            state["response"] = "¿Podrías contarme más detalles sobre tu proyecto para ayudarte mejor?"
            return state