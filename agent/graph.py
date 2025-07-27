# agent/graph.py

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    router_node,
    consultation_node,
    company_info_node,           # Nuevo nodo
    equipment_details_node,      # Nuevo nodo
    analyze_requirements_node,
    recommend_equipment_node,
    collect_documents_node,
    generate_quotation_node,
    send_quotation_node,
    notify_commercial_node,
    process_rut_node
)
import logging

logger = logging.getLogger(__name__)

def create_agent_graph():
    """
    Crea y compila el grafo del agente con una lógica de control de flujo mejorada
    para evitar bucles infinitos y manejar mejor las conversaciones.
    """
    workflow = StateGraph(AgentState)

    # 1. Añadir todos los nodos al grafo
    logger.info("Añadiendo nodos al grafo...")
    print("INFO: Añadiendo nodos al grafo...")
    workflow.add_node("router", router_node)
    workflow.add_node("consultation", consultation_node)
    workflow.add_node("company_info", company_info_node)          # Nuevo nodo
    workflow.add_node("equipment_details", equipment_details_node) # Nuevo nodo
    workflow.add_node("analyze_requirements", analyze_requirements_node)
    workflow.add_node("recommend_equipment", recommend_equipment_node)
    workflow.add_node("collect_documents", collect_documents_node)
    workflow.add_node("process_rut", process_rut_node)
    workflow.add_node("generate_quotation", generate_quotation_node)
    workflow.add_node("send_quotation", send_quotation_node)
    workflow.add_node("notify_commercial", notify_commercial_node)

    # 2. El punto de entrada es siempre el router
    workflow.set_entry_point("router")
    logger.info("Punto de entrada establecido en 'router'")
    print("INFO: Punto de entrada establecido en 'router'")

    # 3. --- ARISTAS CONDICIONALES MEJORADAS ---
    # El router es el único que decide el siguiente paso basado en 'next_node'
    workflow.add_conditional_edges(
        "router",
        lambda state: state.get("next_node", "END"),
        {
            "consultation": "consultation",
            "company_info": "company_info",                   # Nueva ruta
            "equipment_details": "equipment_details",         # Nueva ruta
            "analyze_requirements": "analyze_requirements",
            "collect_documents": "collect_documents",
            "process_rut": "process_rut",
            "generate_quotation": "generate_quotation",
            "send_quotation": "send_quotation",
            "END": END,
            "end": END
        }
    )
    
    # 4. --- CONEXIONES EXPLÍCITAS MEJORADAS ---
    
    # Después de conversar, el agente debe esperar la respuesta del usuario.
    workflow.add_edge("consultation", END)
    
    # Nuevos nodos que también esperan respuesta del usuario
    workflow.add_edge("company_info", END)
    workflow.add_edge("equipment_details", END)
    
    # Después de pedir documentos, también debe esperar.
    workflow.add_edge("collect_documents", END)
    
    # Después de procesar el RUT, SÍ debe volver al router para decidir el siguiente paso.
    workflow.add_edge("process_rut", "router")
    
    # Esta es una secuencia interna correcta.
    workflow.add_edge("analyze_requirements", "recommend_equipment")
    
    # Después de recomendar, esperamos la decisión del usuario.
    workflow.add_edge("recommend_equipment", END)

    # Esta es la secuencia final correcta.
    workflow.add_edge("generate_quotation", "send_quotation")
    workflow.add_edge("send_quotation", "notify_commercial")
    workflow.add_edge("notify_commercial", END)

    logger.info("Arquitectura de flujo de control mejorada")
    print("INFO: Grafo compilado exitosamente")
    
    agent_graph = workflow.compile()
    logger.info("Grafo compilado exitosamente")
    
    return agent_graph

def get_agent():
    """Retorna la instancia del agente compilado."""
    return create_agent_graph()