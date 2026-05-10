import sys
import os
from pathlib import Path

# Ensure repo root is on sys.path so `src.*` imports resolve when Streamlit
# Cloud runs this file directly (it adds src/ui/ but not the project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time
import uuid
import logging

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from src.db.database import get_engine, verify_database
from src.graph.workflow import get_graph

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Music Store Support",
    page_icon="🎵",
    layout="centered",
)


# ── Session state helpers ─────────────────────────────────────────────────────

def _init_session():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "waiting_for_input" not in st.session_state:
        st.session_state.waiting_for_input = False
    if "interrupt_prompt" not in st.session_state:
        st.session_state.interrupt_prompt = ""
    if "db_ready" not in st.session_state:
        with st.spinner("Loading Chinook database…"):
            get_engine()
        st.session_state.db_ready = True


def _reset_session():
    for key in ["thread_id", "chat_history", "waiting_for_input", "interrupt_prompt"]:
        st.session_state.pop(key, None)
    _init_session()


def _get_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _get_interrupt_value(graph_state) -> str | None:
    """Return the interrupt message if the graph is paused, else None."""
    if not graph_state.next:
        return None
    for task in graph_state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            return str(task.interrupts[0].value)
    return None


# ── Main processing ───────────────────────────────────────────────────────────

def _process(user_input: str):
    graph = get_graph()
    config = _get_config()
    start = time.time()

    try:
        if st.session_state.waiting_for_input:
            # Resume from interrupt
            result = graph.invoke(Command(resume=user_input), config=config)
        else:
            result = graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )

        elapsed = round(time.time() - start, 2)
        graph_state = graph.get_state(config)
        interrupt_msg = _get_interrupt_value(graph_state)

        if interrupt_msg:
            st.session_state.waiting_for_input = True
            st.session_state.interrupt_prompt = interrupt_msg
            return interrupt_msg, True, elapsed

        st.session_state.waiting_for_input = False
        st.session_state.interrupt_prompt = ""

        # Extract last AI message
        messages = result.get("messages", [])
        ai_msgs = [m for m in messages if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)]
        reply = ai_msgs[-1].content if ai_msgs else "I processed your request but have no response to display."
        return reply, False, elapsed

    except Exception as e:
        logger.exception("Graph error: %s", e)
        st.session_state.waiting_for_input = False
        return f"An error occurred: {e}", False, 0.0


# ── UI ────────────────────────────────────────────────────────────────────────

def main():
    _init_session()

    st.title("🎵 Music Store Customer Support")
    st.caption("Powered by Multi-Agent AI | Chinook Digital Music Store")

    # Sidebar
    with st.sidebar:
        st.header("Session")
        st.code(f"Thread: {st.session_state.thread_id[:8]}…", language=None)
        if st.button("🔄 New Conversation", use_container_width=True):
            _reset_session()
            st.rerun()

        st.divider()
        st.subheader("Database Status")
        if st.button("Check DB Health", use_container_width=True):
            status = verify_database()
            if status["status"] == "healthy":
                st.success("✅ Healthy")
            else:
                st.warning(f"⚠️ {status['status']}")
            for tbl, info in status.get("tables", {}).items():
                icon = "✅" if info["ok"] else "❌"
                st.caption(f"{icon} {tbl}: {info['actual']} rows")

        st.divider()
        st.caption(
            "**How to verify:** Provide your Customer ID, "
            "email address, or phone number."
        )

    # Chat history
    for entry in st.session_state.chat_history:
        role = entry["role"]
        with st.chat_message(role):
            st.markdown(entry["content"])

    # Verification banner
    if st.session_state.waiting_for_input:
        st.info(f"🔐 **Identity Verification Required**\n\n{st.session_state.interrupt_prompt}")

    # Input
    placeholder = (
        "Enter your Customer ID, email, or phone number…"
        if st.session_state.waiting_for_input
        else "Ask about music, albums, invoices, or purchases…"
    )

    if user_input := st.chat_input(placeholder):
        # Show user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Process
        with st.chat_message("assistant"):
            with st.spinner("Processing…"):
                reply, is_interrupt, elapsed = _process(user_input)

            if is_interrupt:
                st.info(f"🔐 {reply}")
            else:
                st.markdown(reply)
                st.caption(f"⏱ {elapsed}s")

        st.session_state.chat_history.append(
            {"role": "assistant", "content": reply}
        )
        st.rerun()


if __name__ == "__main__":
    main()
