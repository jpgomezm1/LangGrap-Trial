from typing import TypedDict, List, Dict, Optional, Any
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # Información del usuario
    user_id: str
    user_name: Optional[str]
    company_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    
    # Etapa de la conversación
    conversation_stage: str
    
    # Información del proyecto
    project_details: Dict[str, Any]
    
    # Equipos y cotización
    recommended_equipment: List[Dict[str, Any]]
    quotation_data: Optional[Dict[str, Any]]
    
    # Documentos
    documents: Dict[str, Any]
    
    # Historial de mensajes
    messages: List[BaseMessage]
    
    # Control de flujo
    needs_more_info: bool
    ready_for_quotation: bool
    quotation_sent: bool
    commercial_notified: bool
    
    # Mensaje actual del usuario
    current_message: str
    
    # Respuesta a enviar
    response: str