import resend
from config import config
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        resend.api_key = config.RESEND_API_KEY
    
    async def send_commercial_notification(self, conversation_data: Dict[str, Any], quotation_data: Dict[str, Any]):
        """Envía notificación al equipo comercial sobre nueva cotización"""
        
        try:
            # Preparar contenido del email
            equipment_list = ""
            if quotation_data and 'equipment_details' in quotation_data:
                for eq in quotation_data['equipment_details']:
                    equipment_list += f"- {eq['name']}: ${eq['calculated_price']:,.0f}\n"
            
            html_content = f"""
            <h2>Nueva Cotización Generada - EquiposUp</h2>
            
            <h3>Información del Cliente:</h3>
            <ul>
                <li><strong>Nombre:</strong> {conversation_data.get('user_name', 'N/A')}</li>
                <li><strong>Empresa:</strong> {conversation_data.get('company_name', 'N/A')}</li>
                <li><strong>Teléfono:</strong> {conversation_data.get('phone', 'N/A')}</li>
                <li><strong>Email:</strong> {conversation_data.get('email', 'N/A')}</li>
                <li><strong>User ID Telegram:</strong> {conversation_data.get('user_id', 'N/A')}</li>
            </ul>
            
            <h3>Detalles del Proyecto:</h3>
            <p>{conversation_data.get('project_details', {})}</p>
            
            <h3>Equipos Cotizados:</h3>
            <pre>{equipment_list}</pre>
            
            <h3>Total de la Cotización:</h3>
            <p><strong>${quotation_data.get('total_amount', 0):,.0f}</strong></p>
            
            <p>El cliente ha recibido la cotización vía Telegram. Por favor, realizar seguimiento.</p>
            """
            
            # Enviar email
            params = {
                "from": f"Bot EquiposUp <noreply@{config.COMPANY_WEBSITE.replace('https://', '').replace('http://', '')}>",
                "to": [config.COMPANY_EMAIL],
                "subject": f"Nueva Cotización - {conversation_data.get('company_name', 'Cliente')}",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            logger.info(f"Email enviado exitosamente: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email: {e}")
            return False