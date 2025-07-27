import logging
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage  # Asegúrate de importar AIMessage
from agent.state import AgentState
from database.connection import SessionLocal
from database.models import Conversation

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        # El cache en memoria es útil para conversaciones activas y rápidas.
        self.active_conversations = {}

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start, da la bienvenida e inicializa el estado."""
        user_id = str(update.effective_user.id)
        
        # El mensaje de bienvenida ahora es gestionado directamente aquí.
        welcome_message = """¡Bienvenido a EquiposUp! 🏗️

Soy tu asistente virtual especializado en equipos de altura. Estoy aquí para ayudarte a encontrar la solución perfecta para tu proyecto y generar una cotización personalizada.

Para comenzar, simplemente escríbeme contándome sobre tu proyecto. ¡Empecemos! 😊"""
        
        await update.message.reply_text(welcome_message)
        logger.info(f"Usuario {user_id} inició conversación")
        # El estado se creará dinámicamente en el primer mensaje real.
        if user_id in self.active_conversations:
            del self.active_conversations[user_id]

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Maneja mensajes de texto, delega toda la lógica al agente."""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        logger.info(f"Mensaje de usuario {user_id}: {message_text[:50]}...")

        try:
            # 1. Obtener o crear estado de la conversación.
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            # 2. Actualizar estado con el nuevo mensaje del usuario.
            state["current_message"] = message_text
            state["messages"].append(HumanMessage(content=message_text))
            
            # 3. Ejecutar el grafo del agente con la configuración correcta.
            config = {"recursion_limit": 25}
            result = agent_graph.invoke(state, config=config)
            
            # 4. Obtener la respuesta y añadirla al historial.
            response_text = result.get("response", "Lo siento, no pude procesar tu mensaje.")
            result["messages"].append(AIMessage(content=response_text))
            
            # 5. Actualizar el cache con el estado más reciente.
            self.active_conversations[user_id] = result
            
            # 6. Enviar respuesta al usuario.
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}", exc_info=True)
            await update.message.reply_text(
                "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?"
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Maneja documentos enviados, como el RUT."""
        user_id = str(update.effective_user.id)
        
        try:
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            document = update.message.document
            document_name = document.file_name or "documento"
            
            # Lógica para manejar el documento (ej. identificar si es un RUT).
            documents = state.get("documents", {})
            if "rut" in document_name.lower() or "nit" in document_name.lower():
                documents["rut"] = {"file_name": document_name, "file_id": document.file_id, "received": True}
                user_feedback = f"Documento recibido: {document_name}. ¡Gracias! He guardado tu RUT."
            else:
                documents["other"] = {"file_name": document_name, "file_id": document.file_id, "received": True}
                user_feedback = f"Documento {document_name} recibido."
            
            # Actualizar estado y notificar al grafo que se recibió un documento.
            state["documents"] = documents
            state["current_message"] = user_feedback
            state["messages"].append(HumanMessage(content=user_feedback))

            # Ejecutar grafo para que decida el siguiente paso.
            config = {"recursion_limit": 25}
            result = agent_graph.invoke(state, config=config)
            
            response_text = result.get("response", "¡Documento recibido! Déjame ver qué más necesito.")
            result["messages"].append(AIMessage(content=response_text))
            
            self.active_conversations[user_id] = result
            
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando documento: {e}", exc_info=True)
            await update.message.reply_text(
                "Hubo un problema procesando tu documento. ¿Podrías intentar enviarlo de nuevo?"
            )

    async def _get_or_create_conversation_state(self, user_id: str, user) -> AgentState:
        """Obtiene el estado del cache, la BD o crea uno nuevo."""
        if user_id in self.active_conversations:
            return self.active_conversations[user_id]
        
        # (El resto de la función para leer de la BD es correcta, no necesita cambios)
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            if conversation:
                state = AgentState(
                    user_id=user_id,
                    user_name=conversation.user_name or user.first_name,
                    company_name=conversation.company_name,
                    phone=conversation.phone,
                    email=conversation.email,
                    conversation_stage=conversation.stage or "welcome",
                    project_details=conversation.project_details or {},
                    recommended_equipment=conversation.recommended_equipment or [],
                    documents=conversation.documents or {},
                    messages=[], # Se reinicia en cada sesión, pero se podría cargar si se guarda el historial
                    # ... el resto de los campos ...
                )
            else:
                # Crea un estado completamente nuevo si no hay historial
                state = AgentState(
                    user_id=user_id,
                    user_name=user.first_name or "Usuario",
                    messages=[],
                    # ... el resto de campos inicializados en None o valores vacíos ...
                )
            
            self.active_conversations[user_id] = state
            return state
        finally:
            db.close()
            
    # La función _extract_user_info se ha eliminado.