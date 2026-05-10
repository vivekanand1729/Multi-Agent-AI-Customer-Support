import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.prompts import GROUNDING_RULES, MUSIC_AGENT_PROMPT
from src.config.settings import get_llm
from src.models.schemas import SupportState
from src.tools.music_tools import music_tools

logger = logging.getLogger(__name__)


def music_llm_node(state: SupportState) -> dict:
    """LLM step of the hand-built music agent ReAct loop."""
    loaded_memory = state.get("loaded_memory", "")
    memory_context = (
        f"Customer's saved music preferences: {loaded_memory}"
        if loaded_memory
        else "No saved preferences for this customer yet."
    )

    system_prompt = MUSIC_AGENT_PROMPT.format(
        memory_context=memory_context,
        grounding_rules=GROUNDING_RULES,
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    llm = get_llm()
    llm_with_tools = llm.bind_tools(music_tools)
    logger.info("Music agent LLM call — messages count: %d", len(messages))
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def music_tools_node(state: SupportState) -> dict:
    """Tool execution step of the music agent ReAct loop."""
    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in music_tools}

    results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        logger.info("Executing music tool: %s(%s)", tool_name, tool_args)
        try:
            result = tool_map[tool_name].invoke(tool_args)
        except Exception as e:
            result = f"Tool error: {e}"
        results.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )
    return {"messages": results}


def route_music_agent(state: SupportState) -> str:
    """Route within the music ReAct loop: continue if tool calls pending, else done."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "music_tools"
    return "create_memory"
