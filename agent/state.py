from typing import TypedDict, List, Dict, Optional, Any, Sequence, Literal, Annotated
from langchain_core.messages import BaseMessage

# Importar la función add para mensajes
try:
    from operator import add
except ImportError:
    def add(x, y):
        return x + y

class AgentState(TypedDict):
    # --- MANTENER ESTOS CAMPOS ---
    messages: Annotated[Sequence[BaseMessage], add]
    user_name: Optional[str]
    user_id: Optional[str]  # Cambiado de int a str para consistencia con Telegram
    company_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    
    # --- AÑADIR CAMPO NIT ---
    nit: Optional[str]
    
    # Etapa de la conversación
    conversation_stage: str
    
    # Información del proyecto
    project_details: Dict[str, Any]
    
    # Equipos y cotización
    recommended_equipment: List[Dict[str, Any]]
    selected_equipment: Optional[Dict[str, Any]]
    quotation_data: Optional[Dict[str, Any]]
    
    # --- AÑADIR ESTOS NUEVOS CAMPOS DE DOCUMENTOS ---
    documents: Dict[str, Any]
    document_path: Optional[str]
    quotation_pdf_path: Optional[str]
    
    # Historial de mensajes (ya incluido arriba con anotación)
    
    # Control de flujo
    needs_more_info: bool
    ready_for_quotation: bool
    quotation_sent: bool
    commercial_notified: bool
    
    # --- AÑADIR CAMPO PARA INFO DE CLIENTE ---
    client_info: Optional[Dict[str, Any]]
    
    # Mensaje actual del usuario
    current_message: str
    
    # Respuesta a enviar
    response: str
    
    # --- AÑADIR CAMPOS PARA CONTROLAR RESPUESTA DE TELEGRAM ---
    response_type: Literal["text", "document", "end_conversation"]
    document_to_send: Optional[str]
    final_message: Optional[str]
    
    # Campo para el router centralizado
    next_node: str