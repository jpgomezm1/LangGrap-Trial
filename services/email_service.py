import resend
from config import config
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        if config.RESEND_API_KEY:
            resend.api_key = config.RESEND_API_KEY
        else:
            logger.warning("RESEND_API_KEY no configurado, servicio de email deshabilitado")
    
    async def send_commercial_notification(self, conversation_data: Dict[str, Any], quotation_data: Dict[str, Any]):
        """Envía notificación al equipo comercial sobre nueva cotización"""
        
        if not config.RESEND_API_KEY:
            logger.warning("No se puede enviar email: RESEND_API_KEY no configurado")
            return False
        
        try:
            # Preparar contenido del email
            equipment_list = ""
            if quotation_data and 'equipment_details' in quotation_data:
                for eq in quotation_data['equipment_details']:
                    equipment_list += f"- {eq['name']}: ${eq['calculated_price']:,.0f}\n"
            
            # Información del proyecto
            project_info = conversation_data.get('project_details', {})
            project_summary = f"""
Altura requerida: {project_info.get('height', 'N/A')} metros
Tipo de trabajo: {project_info.get('work_type', 'N/A')}
Duración: {project_info.get('duration_text', 'N/A')}
"""
            
            html_content = f"""
            <h2>Nueva Cotización Generada - {config.COMPANY_NAME}</h2>
            
            <h3>Información del Cliente:</h3>
            <ul>
                <li><strong>Nombre:</strong> {conversation_data.get('user_name', 'N/A')}</li>
                <li><strong>Empresa:</strong> {conversation_data.get('company_name', 'N/A')}</li>
                <li><strong>Teléfono:</strong> {conversation_data.get('phone', 'N/A')}</li>
                <li><strong>Email:</strong> {conversation_data.get('email', 'N/A')}</li>
                <li><strong>User ID Telegram:</strong> {conversation_data.get('user_id', 'N/A')}</li>
            </ul>
            
            <h3>Detalles del Proyecto:</h3>
            <pre>{project_summary}</pre>
            
            <h3>Equipos Cotizados:</h3>
            <pre>{equipment_list}</pre>
            
            <h3>Total de la Cotización:</h3>
            <p><strong>${quotation_data.get('total_amount', 0):,.0f} COP</strong></p>
            
            <h3>Próximos pasos:</h3>
            <p>✅ El cliente ha recibido la cotización vía Telegram.</p>
            <p>📞 Por favor, realizar seguimiento telefónico en las próximas 2 horas.</p>
            <p>📧 Considerar envío de cotización formal por email si el cliente lo solicita.</p>
            
            <hr>
            <p><small>Generado automáticamente por el sistema de cotizaciones de {config.COMPANY_NAME}</small></p>
            """
            
            # Determinar el dominio para el email
            email_domain = config.COMPANY_DOMAIN
            if email_domain.startswith('http'):
                email_domain = email_domain.replace('https://', '').replace('http://', '')
            
            # Enviar email
            params = {
                "from": f"Bot {config.COMPANY_NAME} <noreply@{email_domain}>",
                "to": [config.COMPANY_EMAIL],
                "subject": f"Nueva Cotización - {conversation_data.get('company_name', 'Cliente')} - ${quotation_data.get('total_amount', 0):,.0f}",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            logger.info(f"Email comercial enviado exitosamente: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email comercial: {e}")
            return False
    
    async def send_quotation_to_client(self, client_email: str, quotation_data: Dict[str, Any], pdf_attachment_path: str = None):
        """Envía la cotización directamente al cliente por email (opcional)"""
        
        if not config.RESEND_API_KEY:
            logger.warning("No se puede enviar email: RESEND_API_KEY no configurado")
            return False
        
        if not client_email:
            logger.warning("No se puede enviar email: email del cliente no proporcionado")
            return False
        
        try:
            # Preparar contenido del email para el cliente
            html_content = f"""
            <h2>Cotización - {config.COMPANY_NAME}</h2>
            
            <p>Estimado cliente,</p>
            
            <p>Adjunto encontrará la cotización solicitada para su proyecto de equipos de altura.</p>
            
            <h3>Resumen de la Cotización:</h3>
            <p><strong>Total: ${quotation_data.get('total_amount', 0):,.0f} COP</strong></p>
            
            <h3>Condiciones:</h3>
            <ul>
                <li>✅ Precios válidos por 15 días</li>
                <li>✅ Incluye entrega y recogida en Bogotá</li>
                <li>✅ Capacitación básica incluida</li>
                <li>✅ Soporte técnico 24/7</li>
            </ul>
            
            <p>Para proceder con el alquiler o resolver cualquier duda, puede contactarnos:</p>
            <ul>
                <li>📞 Teléfono: {config.COMPANY_PHONE}</li>
                <li>📧 Email: {config.COMPANY_EMAIL}</li>
                <li>🌐 Web: {config.COMPANY_DOMAIN}</li>
            </ul>
            
            <p>¡Gracias por confiar en {config.COMPANY_NAME}!</p>
            
            <hr>
            <p><small>{config.COMPANY_NAME} - Equipos de Altura Profesionales</small></p>
            """
            
            # Determinar el dominio para el email
            email_domain = config.COMPANY_DOMAIN
            if email_domain.startswith('http'):
                email_domain = email_domain.replace('https://', '').replace('http://', '')
            
            # Preparar parámetros del email
            params = {
                "from": f"{config.COMPANY_NAME} <ventas@{email_domain}>",
                "to": [client_email],
                "subject": f"Cotización de Equipos de Altura - {config.COMPANY_NAME}",
                "html": html_content
            }
            
            # Adjuntar PDF si se proporciona
            if pdf_attachment_path and os.path.exists(pdf_attachment_path):
                try:
                    with open(pdf_attachment_path, 'rb') as pdf_file:
                        pdf_content = pdf_file.read()
                        params["attachments"] = [{
                            "filename": f"Cotizacion_{config.COMPANY_NAME}.pdf",
                            "content": pdf_content
                        }]
                except Exception as e:
                    logger.warning(f"No se pudo adjuntar PDF: {e}")
            
            response = resend.Emails.send(params)
            logger.info(f"Email de cotización enviado al cliente {client_email}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email al cliente: {e}")
            return False
    
    def test_email_configuration(self):
        """Prueba la configuración de email"""
        if not config.RESEND_API_KEY:
            return {"status": "error", "message": "RESEND_API_KEY no configurado"}
        
        try:
            # Enviar email de prueba
            email_domain = config.COMPANY_DOMAIN
            if email_domain.startswith('http'):
                email_domain = email_domain.replace('https://', '').replace('http://', '')
            
            params = {
                "from": f"Test {config.COMPANY_NAME} <noreply@{email_domain}>",
                "to": [config.COMPANY_EMAIL],
                "subject": f"Prueba de configuración - {config.COMPANY_NAME}",
                "html": f"""
                <h2>Prueba de Email</h2>
                <p>Esta es una prueba de la configuración de email para {config.COMPANY_NAME}.</p>
                <p>Si recibe este email, la configuración está funcionando correctamente.</p>
                """
            }
            
            response = resend.Emails.send(params)
            return {"status": "success", "message": f"Email de prueba enviado: {response}"}
            
        except Exception as e:
            return {"status": "error", "message": f"Error en prueba de email: {e}"}