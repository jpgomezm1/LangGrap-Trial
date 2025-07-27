# agent/graph.py

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    router_node,
    consultation_node,
    analyze_requirements_node,
    recommend_equipment_node,
    collect_documents_node,
    generate_quotation_node,
    send_quotation_node,
    notify_commercial_node
)
import logging

logger = logging.getLogger(__name__)

def create_agent_graph():
    """Crea y compila el grafo del agente con el flujo de control final."""
    
    workflow = StateGraph(AgentState)

    # 1. Añadir todos los nodos al grafo
    logger.info("Añadiendo nodos al grafo...")
    workflow.add_node("router", router_node)
    workflow.add_node("consultation", consultation_node)
    workflow.add_node("analyze_requirements", analyze_requirements_node)
    workflow.add_node("recommend_equipment", recommend_equipment_node)
    workflow.add_node("collect_documents", collect_documents_node)
    workflow.add_node("generate_quotation", generate_quotation_node)
    workflow.add_node("send_quotation", send_quotation_node)
    workflow.add_node("notify_commercial", notify_commercial_node)

    # 2. El punto de entrada es siempre el ROUTER
    workflow.set_entry_point("router")
    logger.info("Punto de entrada establecido en 'router'")

    # 3. Arista condicional desde el ROUTER
    workflow.add_conditional_edges(
        "router",
        lambda state: state.get("next_node", "END"),
        {
            "consultation": "consultation",
            "analyze_requirements": "analyze_requirements",
            "collect_documents": "collect_documents",
            "generate_quotation": "generate_quotation",
            "END": END 
        }
    )
    
    # 4. Definir las transiciones desde los nodos de trabajo
    
    # Nodos que preguntan algo al usuario y DEBEN TERMINAR el turno.
    workflow.add_edge("consultation", END)
    workflow.add_edge("recommend_equipment", END)
    workflow.add_edge("collect_documents", END)
    workflow.add_edge("notify_commercial", END)
    
    # Secuencias internas que no requieren interacción del usuario.
    workflow.add_edge("analyze_requirements", "recommend_equipment") 
    workflow.add_edge("generate_quotation", "send_quotation")
    workflow.add_edge("send_quotation", "notify_commercial")

    logger.info("Arquitectura de flujo de control final configurada")

    # 5. Compilar el grafo
    agent_graph = workflow.compile()
    logger.info("Grafo compilado exitosamente")
    
    return agent_graph