import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import config
from database.connection import create_tables
from services.telegram_service import TelegramService
from services.equipment_service import EquipmentService
from services.email_service import EmailService
from agent.graph import create_agent_graph

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramAgentBot:
    def __init__(self):
        self.telegram_service = TelegramService()
        self.equipment_service = EquipmentService()
        self.email_service = EmailService()
        self.agent_graph = None
        
        # Inicializar base de datos y datos de ejemplo
        self._initialize_database()
        
        # Crear grafo del agente
        self.agent_graph = create_agent_graph()
        logger.info("Agente inicializado correctamente")
    
    def _initialize_database(self):
        """Inicializa la base de datos y datos de ejemplo"""
        try:
            # Crear tablas
            create_tables()
            logger.info("Tablas de base de datos creadas/verificadas")
            
            # Agregar equipos de ejemplo si no existen
            self.equipment_service.seed_sample_equipment()
            logger.info("Datos de ejemplo verificados")
            
        except Exception as e:
            logger.error(f"Error inicializando base de datos: {e}")
            raise
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start"""
        try:
            await self.telegram_service.handle_start(update, context)
            logger.info(f"Usuario {update.effective_user.id} inició conversación")
        except Exception as e:
            logger.error(f"Error en comando start: {e}")
            await update.message.reply_text(
                "Hubo un problema iniciando la conversación. Por favor intenta de nuevo con /start"
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja todos los mensajes de texto"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            logger.info(f"Mensaje de usuario {user_id}: {message_text[:50]}...")
            
            await self.telegram_service.handle_message(update, context, self.agent_graph)
            
        except Exception as e:
            logger.error(f"Error manejando mensaje: {e}")
            await update.message.reply_text(
                "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?"
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja documentos enviados por el usuario"""
        try:
            user_id = update.effective_user.id
            doc_name = update.message.document.file_name or "documento"
            logger.info(f"Documento recibido de usuario {user_id}: {doc_name}")
            
            await self.telegram_service.handle_document(update, context, self.agent_graph)
            
        except Exception as e:
            logger.error(f"Error manejando documento: {e}")
            await update.message.reply_text(
                "Hubo un problema procesando tu documento. ¿Podrías intentar enviarlo de nuevo?"
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja errores globales"""
        logger.error(f"Update {update} causó error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Ocurrió un error inesperado. Por favor, intenta de nuevo o contacta a soporte."
            )
    
    def run(self):
        """Inicia el bot"""
        try:
            logger.info("Iniciando bot de Telegram...")
            
            # Verificar configuración
            if not config.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN no configurado")
            if not config.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY no configurado")
            
            # Crear aplicación de Telegram
            application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            
            # Agregar handlers
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
            
            # Agregar handler de errores
            application.add_error_handler(self.error_handler)
            
            logger.info("Bot configurado correctamente")
            logger.info(f"Bot iniciado - Empresa: {config.COMPANY_NAME}")
            logger.info(f"URL de la empresa: {config.COMPANY_WEBSITE}")
            
            # Ejecutar el bot
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Error fatal iniciando bot: {e}")
            raise

if __name__ == "__main__":
    try:
        bot = TelegramAgentBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error crítico: {e}")