import logging

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agents.prompts import INVOICE_AGENT_PROMPT
from src.config.settings import get_llm
from src.models.schemas import SupportState
from src.tools.invoice_tools import invoice_tools

logger = logging.getLogger(__name__)

_invoice_graph = None


def _get_invoice_graph():
    global _invoice_graph
    if _invoice_graph is None:
        llm = get_llm()
        _invoice_graph = create_react_agent(
            llm,
            invoice_tools,
            prompt=SystemMessage(content=INVOICE_AGENT_PROMPT),
        )
    return _invoice_graph


def invoice_agent_node(state: SupportState) -> dict:
    """Invoke the pre-built invoice ReAct agent and return its new messages."""
    graph = _get_invoice_graph()
    original_len = len(state["messages"])

    logger.info("Invoice agent invoked — message history length: %d", original_len)
    result = graph.invoke({"messages": list(state["messages"])})

    new_messages = result["messages"][original_len:]
    logger.info("Invoice agent produced %d new messages", len(new_messages))
    return {"messages": new_messages}
