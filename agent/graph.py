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
    notify_commercial_node,
    router_node
)

def create_agent_graph():
    """Crea y retorna el grafo del agente con arquitectura simplificada"""
    
    # Crear el grafo
    workflow = StateGraph(AgentState)
    
    # Agregar nodos
    workflow.add_node("welcome", welcome_node)
    workflow.add_node("router", router_node)
    workflow.add_node("consultation", consultation_node)
    workflow.add_node("analyze_requirements", analyze_requirements_node)
    workflow.add_node("recommend_equipment", recommend_equipment_node)
    workflow.add_node("collect_documents", collect_documents_node)
    workflow.add_node("generate_quotation", generate_quotation_node)
    workflow.add_node("send_quotation", send_quotation_node)
    workflow.add_node("notify_commercial", notify_commercial_node)
    
    # Definir punto de entrada
    workflow.set_entry_point("welcome")
    
    # Simplificar el flujo: cada nodo va al router, y el router decide el siguiente paso
    workflow.add_edge("welcome", "router")
    workflow.add_edge("consultation", "router")
    workflow.add_edge("analyze_requirements", "router")
    workflow.add_edge("recommend_equipment", "router")
    workflow.add_edge("collect_documents", "router")
    workflow.add_edge("generate_quotation", "router")
    workflow.add_edge("send_quotation", "router")
    
    # El router tiene salidas condicionales a todos los nodos posibles
    workflow.add_conditional_edges(
        "router",
        lambda state: state.get("next_node", "END"),
        {
            "consultation": "consultation",
            "analyze_requirements": "analyze_requirements",
            "recommend_equipment": "recommend_equipment",
            "collect_documents": "collect_documents",
            "generate_quotation": "generate_quotation",
            "send_quotation": "send_quotation",
            "notify_commercial": "notify_commercial",
            "END": END
        }
    )
    
    # El notify_commercial va directamente a END
    workflow.add_edge("notify_commercial", END)
    
    # Compilar el grafo
    return workflow.compile()