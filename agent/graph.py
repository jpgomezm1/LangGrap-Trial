from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    welcome_node,
    consultation_node,
    analyze_requirements_node,
    recommend_equipment_node,
    collect_documents_node,
    generate_quotation_node,
    send_quotation_node,
    notify_commercial_node
)

def should_continue_consultation(state: AgentState) -> str:
    """Determina si continuar consultando o pasar al análisis"""
    if state.get('needs_more_info', True):
        return "consultation"
    else:
        return "analyze_requirements"

def should_continue_after_recommendation(state: AgentState) -> str:
    """Determina el siguiente paso después de las recomendaciones"""
    # Evitar bucle infinito - si ya está en equipment_selected, ir a documentos
    if state.get('conversation_stage') == "equipment_selected":
        return "collect_documents"
    
    current_message = state.get('current_message', '').lower()
    
    # Si el usuario acepta o muestra interés
    if any(word in current_message for word in ['me gusta', 'perfecto', 'si', 'sí', 'bien', 'acepto', 'cotización', 'interesa']):
        return "collect_documents"
    
    # Si el usuario tiene más preguntas o quiere más opciones
    if any(word in current_message for word in ['más', 'otro', 'diferente', 'pregunta', 'duda']):
        return "recommend_equipment"
    
    # Por defecto ir a documentos para evitar bucle
    return "collect_documents"

def has_required_documents(state: AgentState) -> str:
    """Verifica si se tienen los documentos necesarios"""
    documents = state.get('documents', {})
    
    has_rut = 'rut' in documents
    has_phone = state.get('phone') is not None
    has_email = state.get('email') is not None
    
    if has_rut and has_phone and has_email:
        return "generate_quotation"
    else:
        return "collect_documents"

def route_from_consultation(state: AgentState) -> str:
    """Enruta desde consultation - evita bucles"""
    # Si ya pasó por consultation suficientes veces, forzar avance
    stage = state.get('conversation_stage', '')
    if stage in ['analyzing_requirements', 'recommending_equipment', 'equipment_selected']:
        return "analyze_requirements"
    
    if state.get('needs_more_info', True):
        return "consultation"
    else:
        return "analyze_requirements"

def create_agent_graph():
    """Crea y retorna el grafo del agente"""
    
    # Crear el grafo
    workflow = StateGraph(AgentState)
    
    # Agregar nodos
    workflow.add_node("welcome", welcome_node)
    workflow.add_node("consultation", consultation_node)
    workflow.add_node("analyze_requirements", analyze_requirements_node)
    workflow.add_node("recommend_equipment", recommend_equipment_node)
    workflow.add_node("collect_documents", collect_documents_node)
    workflow.add_node("generate_quotation", generate_quotation_node)
    workflow.add_node("send_quotation", send_quotation_node)
    workflow.add_node("notify_commercial", notify_commercial_node)
    
    # Definir punto de entrada
    workflow.set_entry_point("welcome")
    
    # Agregar bordes condicionales con lógica mejorada
    workflow.add_conditional_edges(
        "consultation",
        route_from_consultation,
        {
            "consultation": "consultation",
            "analyze_requirements": "analyze_requirements"
        }
    )
    
    workflow.add_conditional_edges(
        "recommend_equipment",
        should_continue_after_recommendation,
        {
            "recommend_equipment": "recommend_equipment",
            "collect_documents": "collect_documents"
        }
    )
    
    workflow.add_conditional_edges(
        "collect_documents",
        has_required_documents,
        {
            "collect_documents": "collect_documents",
            "generate_quotation": "generate_quotation"
        }
    )
    
    # Agregar bordes normales
    workflow.add_edge("welcome", "consultation")
    workflow.add_edge("analyze_requirements", "recommend_equipment")
    workflow.add_edge("generate_quotation", "send_quotation")
    workflow.add_edge("send_quotation", "notify_commercial")
    workflow.add_edge("notify_commercial", END)
    
    # Compilar el grafo (solo con argumentos válidos)
    return workflow.compile()