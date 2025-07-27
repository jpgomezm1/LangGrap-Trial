import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from database.connection import SessionLocal
from database.models import Conversation, Message

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

    # --- MODIFICA handle_message PARA USAR EL NUEVO MÉTODO ---
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Maneja mensajes de texto, delega toda la lógica al agente."""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        logger.info(f"Mensaje de usuario {user_id}: {message_text[:50]}...")
        print(f"INFO: Mensaje de usuario {user_id}: {message_text[:50]}...")

        try:
            # 1. Obtener o crear estado de la conversación.
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            # 2. Actualizar estado con el nuevo mensaje del usuario.
            state["current_message"] = message_text
            state["messages"].append(HumanMessage(content=message_text))
            
            # 3. Usar el nuevo método auxiliar
            await self._invoke_agent_and_reply(state, update, context, agent_graph)
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}", exc_info=True)
            await update.message.reply_text(
                "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?"
            )

    # --- REEMPLAZA TU handle_document CON ESTE ---
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """
        Gestiona la recepción de documentos (específicamente el RUT en PDF).
        """
        user_id = str(update.effective_user.id)
        
        try:
            print(f"INFO: Documento recibido de usuario {user_id}: {update.message.document.file_name}")

            # 1. Crear un directorio temporal para guardar los documentos si no existe
            doc_dir = "documentos_recibidos"
            os.makedirs(doc_dir, exist_ok=True)
            
            # 2. Descargar el archivo
            document = update.message.document
            file = await context.bot.get_file(document.file_id)
            file_path = os.path.join(doc_dir, f"{user_id}_{document.file_name}")
            await file.download_to_drive(file_path)
            
            logger.info(f"Documento de {user_id} guardado en: {file_path}")
            print(f"INFO: Documento de {user_id} guardado en: {file_path}")

            # 3. Preparar el estado para invocar al agente
            state = await self._get_or_create_conversation_state(user_id, update.effective_user)
            
            document_name = document.file_name or "documento"
            
            # 4. Lógica para manejar el documento (ej. identificar si es un RUT).
            documents = state.get("documents", {})
            if "rut" in document_name.lower() or "nit" in document_name.lower():
                documents["rut"] = {
                    "file_name": document_name, 
                    "file_id": document.file_id, 
                    "file_path": file_path,  # Añadimos la ruta del archivo
                    "received": True
                }
                user_feedback = f"Documento recibido: {document_name}. ¡Gracias! He guardado tu RUT."
            else:
                documents["other"] = {
                    "file_name": document_name, 
                    "file_id": document.file_id, 
                    "file_path": file_path,
                    "received": True
                }
                user_feedback = f"Documento {document_name} recibido."
            
            # 5. Actualizar estado y notificar al grafo que se recibió un documento.
            state["documents"] = documents
            state["document_path"] = file_path  # <-- CLAVE: Añadimos la ruta del PDF al estado
            state["current_message"] = user_feedback
            state["messages"].append(HumanMessage(content=user_feedback))

            # 6. Usar el nuevo método auxiliar
            await self._invoke_agent_and_reply(state, update, context, agent_graph)
            
        except Exception as e:
            logger.error(f"Error procesando documento: {e}", exc_info=True)
            await update.message.reply_text(
                "Hubo un problema procesando tu documento. ¿Podrías intentar enviarlo de nuevo?"
            )

    # --- CREA ESTE NUEVO MÉTODO AUXILIAR ---
    async def _invoke_agent_and_reply(self, state: AgentState, update: Update, context: ContextTypes.DEFAULT_TYPE, agent_graph):
        """Método auxiliar que invoca al agente y maneja la respuesta."""
        user_id = state['user_id']
        
        try:
            # 1. Guardar el mensaje del usuario en la base de datos
            await self._save_message_to_db(user_id, "user", state["current_message"])
            
            # 2. Ejecutar el grafo del agente con la configuración correcta.
            config = {"recursion_limit": 25}
            result = agent_graph.invoke(state, config=config)
            
            # 3. Obtener la respuesta y añadirla al historial.
            response_text = result.get("response", "Lo siento, no pude procesar tu mensaje.")
            result["messages"].append(AIMessage(content=response_text))
            
            # 4. Guardar el mensaje del agente en la base de datos
            await self._save_message_to_db(user_id, "agent", response_text)
            
            # 5. Actualizar el cache con el estado más reciente.
            self.active_conversations[user_id] = result
            
            # 6. Lógica para enviar texto o documento
            if result.get("response_type") == "document" and result.get("document_to_send"):
                document_path = result["document_to_send"]
                caption = result.get("final_message", "Aquí tienes tu cotización.")
                
                try:
                    # Enviar el documento PDF
                    with open(document_path, 'rb') as doc_file:
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id,
                            document=doc_file,
                            caption=caption,
                            filename=os.path.basename(document_path)
                        )
                    logger.info(f"Cotización en PDF enviada a {user_id}")
                    print(f"INFO: Cotización en PDF enviada a {user_id}")
                    # Opcional: limpiar el archivo PDF después de enviarlo
                    # os.remove(document_path)
                except FileNotFoundError:
                    logger.error(f"Error: No se encontró el archivo PDF en {document_path}")
                    print(f"❌ Error: No se encontró el archivo PDF en {document_path}")
                    await update.message.reply_text("Lo siento, no pude encontrar el archivo de la cotización para enviártelo.")
                except Exception as e:
                    logger.error(f"Error al enviar el documento a {user_id}: {e}")
                    await update.message.reply_text("Tuve un problema al enviar el documento. Ya notifiqué al equipo.")

            # Si no es un documento, enviar una respuesta de texto normal
            else:
                await update.message.reply_text(response_text)
                
        except Exception as e:
            logger.error(f"Error en _invoke_agent_and_reply: {e}", exc_info=True)
            await update.message.reply_text("Disculpa, tuve un problema procesando tu solicitud.")

    async def _get_or_create_conversation_state(self, user_id: str, user) -> AgentState:
        """Obtiene el estado del cache, la BD o crea uno nuevo."""
        if user_id in self.active_conversations:
            return self.active_conversations[user_id]
        
        state = await self._get_current_state_for_user(user_id, user)
        self.active_conversations[user_id] = state
        return state

    async def _get_current_state_for_user(self, user_id: str, user) -> AgentState:
        """Obtiene el estado actual de la conversación desde la base de datos."""
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            
            if conversation:
                # Cargar el historial de mensajes desde la base de datos
                messages = db.query(Message).filter(
                    Message.conversation_id == conversation.id
                ).order_by(Message.created_at).all()
                
                # Convertir mensajes de BD a formato de LangChain
                langchain_messages = []
                for msg in messages:
                    if msg.sender == "user":
                        langchain_messages.append(HumanMessage(content=msg.content))
                    else:
                        langchain_messages.append(AIMessage(content=msg.content))
                
                state = AgentState(
                    user_id=user_id,
                    conversation_id=conversation.id,
                    user_name=conversation.user_name or user.first_name,
                    company_name=conversation.company_name,
                    phone=conversation.phone,
                    email=conversation.email,
                    conversation_stage=conversation.stage or "welcome",
                    project_details=conversation.project_details or {},
                    recommended_equipment=conversation.recommended_equipment or [],
                    documents=conversation.documents or {},
                    messages=langchain_messages,
                    quotation_sent=conversation.quotation_sent or False,
                    commercial_notified=conversation.commercial_notified or False,
                    needs_more_info=False,
                    ready_for_quotation=False,
                    current_message="",
                    response="",
                    next_node="consultation"
                )
            else:
                # Crear nueva conversación en la BD
                new_conversation = Conversation(
                    user_id=user_id,
                    user_name=user.first_name or "Usuario",
                    stage="welcome"
                )
                db.add(new_conversation)
                db.commit()
                db.refresh(new_conversation)
                
                # Crea un estado completamente nuevo
                state = AgentState(
                    user_id=user_id,
                    conversation_id=new_conversation.id,
                    user_name=user.first_name or "Usuario",
                    messages=[],
                    conversation_stage="welcome",
                    project_details={},
                    recommended_equipment=[],
                    documents={},
                    quotation_sent=False,
                    commercial_notified=False,
                    needs_more_info=False,
                    ready_for_quotation=False,
                    current_message="",
                    response="",
                    next_node="consultation"
                )
            
            return state
            
        finally:
            db.close()

    async def _save_message_to_db(self, user_id: str, sender: str, content: str):
        """Guarda un mensaje individual en la base de datos."""
        db = SessionLocal()
        try:
            # Buscar la conversación
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            
            if conversation:
                # Crear y guardar el mensaje
                new_message = Message(
                    conversation_id=conversation.id,
                    sender=sender,
                    content=content
                )
                db.add(new_message)
                db.commit()
                logger.info(f"Mensaje guardado en BD - Usuario: {user_id}, Sender: {sender}")
            else:
                logger.warning(f"No se encontró conversación para usuario {user_id}")
                
        except Exception as e:
            logger.error(f"Error guardando mensaje en BD: {e}")
            db.rollback()
        finally:
            db.close()

    async def _save_conversation_state(self, user_id: str, state: AgentState):
        """Guarda el estado completo de la conversación en la base de datos."""
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(Conversation.user_id == user_id).first()
            
            if conversation:
                # Actualizar conversación existente
                conversation.user_name = state.get('user_name')
                conversation.company_name = state.get('company_name')
                conversation.phone = state.get('phone')
                conversation.email = state.get('email')
                conversation.project_details = state.get('project_details')
                conversation.recommended_equipment = state.get('recommended_equipment')
                conversation.stage = state.get('conversation_stage')
                conversation.documents = state.get('documents')
                conversation.quotation_sent = state.get('quotation_sent', False)
                conversation.commercial_notified = state.get('commercial_notified', False)
                
                db.commit()
                logger.info(f"Estado de conversación actualizado para usuario {user_id}")
            else:
                logger.warning(f"No se encontró conversación para actualizar - Usuario: {user_id}")
                
        except Exception as e:
            logger.error(f"Error guardando estado de conversación: {e}")
            db.rollback()
        finally:
            db.close()

    # Método para limpiar conversaciones inactivas del cache
    def cleanup_inactive_conversations(self, max_inactive_time: int = 3600):
        """Limpia conversaciones inactivas del cache después de cierto tiempo."""
        # Implementación opcional para gestión de memoria
        pass