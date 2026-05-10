import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

from src.agents.music_agent import music_llm_node, music_tools_node, route_music_agent
from src.agents.invoice_agent import invoice_agent_node
from src.agents.prompts import MEMORY_EXTRACTION_PROMPT
from src.agents.supervisor import (
    reject_node,
    route_after_invoice,
    route_after_verify,
    route_supervisor,
    supervisor_node,
    verify_info_node,
)
from src.config.settings import get_llm
from src.models.schemas import MemoryExtraction, SupportState, UserProfile

logger = logging.getLogger(__name__)

# Module-level store and checkpointer (shared across all sessions)
_store = InMemoryStore()
_checkpointer = MemorySaver()
_graph = None


# ── Memory nodes ─────────────────────────────────────────────────────────────

def load_memory_node(state: SupportState, store: BaseStore) -> dict:
    """Load saved customer preferences into state before routing."""
    customer_id = state.get("customer_id")
    if not customer_id:
        return {"loaded_memory": ""}

    namespace = ("memory_profile", customer_id)
    try:
        item = store.get(namespace, "user_memory")
        if item and item.value:
            profile = UserProfile(**item.value)
            if profile.music_preferences:
                loaded = "Customer's saved music preferences: " + ", ".join(profile.music_preferences)
                logger.info("Loaded memory for customer %s: %s", customer_id, loaded)
                return {"loaded_memory": loaded}
    except Exception as e:
        logger.warning("Failed to load memory for customer %s: %s", customer_id, e)

    return {"loaded_memory": ""}


def create_memory_node(state: SupportState, store: BaseStore) -> dict:
    """Extract explicit preferences from the conversation and merge with stored profile."""
    customer_id = state.get("customer_id")
    if not customer_id:
        return {}

    messages = list(state["messages"])[-8:]  # Use recent context
    llm = get_llm()
    structured = llm.with_structured_output(MemoryExtraction)

    extract_messages = [
        SystemMessage(content=MEMORY_EXTRACTION_PROMPT),
        HumanMessage(
            content="Conversation:\n"
            + "\n".join(
                f"{type(m).__name__}: {m.content}"
                for m in messages
                if hasattr(m, "content") and m.content
            )
        ),
    ]

    try:
        extracted = structured.invoke(extract_messages)
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)
        return {}

    if not extracted.music_preferences:
        logger.info("No new preferences extracted for customer %s", customer_id)
        return {}

    namespace = ("memory_profile", customer_id)
    existing_prefs: set[str] = set()
    try:
        item = store.get(namespace, "user_memory")
        if item and item.value:
            existing_prefs = set(UserProfile(**item.value).music_preferences)
    except Exception:
        pass

    merged = existing_prefs | set(p.lower() for p in extracted.music_preferences)
    new_profile = UserProfile(customer_id=customer_id, music_preferences=sorted(merged))
    store.put(namespace, "user_memory", new_profile.model_dump())
    logger.info(
        "Saved preferences for customer %s: %s", customer_id, new_profile.music_preferences
    )
    return {}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    global _graph
    if _graph is not None:
        return _graph

    workflow = StateGraph(SupportState)

    # Nodes
    workflow.add_node("verify_info", verify_info_node)
    workflow.add_node("load_memory", load_memory_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("music_llm", music_llm_node)
    workflow.add_node("music_tools", music_tools_node)
    workflow.add_node("invoice_agent", invoice_agent_node)
    workflow.add_node("reject", reject_node)
    workflow.add_node("create_memory", create_memory_node)

    # Entry
    workflow.add_edge(START, "verify_info")

    # Verify: loop back until verified
    workflow.add_conditional_edges(
        "verify_info",
        route_after_verify,
        {"load_memory": "load_memory", "verify_info": "verify_info"},
    )

    # After memory load → supervisor
    workflow.add_edge("load_memory", "supervisor")

    # Supervisor routes
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "music_llm": "music_llm",
            "invoice_agent": "invoice_agent",
            "reject": "reject",
        },
    )

    # Music ReAct loop
    workflow.add_conditional_edges(
        "music_llm",
        route_music_agent,
        {"music_tools": "music_tools", "create_memory": "create_memory"},
    )
    workflow.add_edge("music_tools", "music_llm")

    # Invoice → maybe music (mixed) → memory
    workflow.add_conditional_edges(
        "invoice_agent",
        route_after_invoice,
        {"music_llm": "music_llm", "create_memory": "create_memory"},
    )

    # Reject and create_memory both end
    workflow.add_edge("reject", END)
    workflow.add_edge("create_memory", END)

    _graph = workflow.compile(checkpointer=_checkpointer, store=_store)
    logger.info("LangGraph compiled successfully")
    return _graph


def get_graph():
    return build_graph()
