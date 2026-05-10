import sys
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

from src.db.database import get_engine, run_query_safe, verify_database
from src.graph.workflow import get_graph

import json

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Music Store Support",
    page_icon="🎵",
    layout="centered",
)

AGENT_LABELS = {
    "music":     ("🎵", "Maya · Music Agent",   "#1DB954"),
    "invoice":   ("🧾", "Alex · Invoice Agent",  "#1E90FF"),
    "mixed":     ("🎵🧾", "Maya & Alex",          "#9B59B6"),
    "off_topic": ("🚫", "Out of scope",           "#E74C3C"),
}

SUGGESTIONS_ANONYMOUS = [
    "What genres do you have?",
    "List Rock artists",
    "What albums does AC/DC have?",
    "Show me Jazz songs",
    "Search songs with 'love' in the title",
    "What artists are in the Metal genre?",
]

SUGGESTIONS_VERIFIED = [
    "Show my invoices",
    "What tracks did I purchase?",
    "What albums does Led Zeppelin have?",
    "Show me Blues artists",
    "Recommend something similar to what I bought",
    "Show line items for my latest invoice",
]


# ── Session state helpers ─────────────────────────────────────────────────────

def _init_session():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "chat_history": [],
        "waiting_for_input": False,
        "interrupt_prompt": "",
        "pending_input": None,
        "verified_customer": None,   # {"id": str, "name": str}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if "db_ready" not in st.session_state:
        with st.spinner("Loading Chinook database…"):
            get_engine()
        st.session_state.db_ready = True


def _reset_session():
    for key in list(st.session_state.keys()):
        if key != "db_ready":
            del st.session_state[key]
    _init_session()


def _get_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _get_interrupt_value(graph_state) -> str | None:
    if not graph_state.next:
        return None
    for task in graph_state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            return str(task.interrupts[0].value)
    return None


def _fetch_customer_name(customer_id: str) -> str:
    rows = json.loads(
        run_query_safe(
            "SELECT FirstName || ' ' || LastName AS Name FROM Customer WHERE CustomerId = :cid",
            {"cid": int(customer_id)},
        )
    )
    return rows[0]["Name"] if rows else f"Customer #{customer_id}"


def _sync_verified_state(graph_state):
    """Pull verified customer info from graph state into session state."""
    if st.session_state.verified_customer:
        return
    values = graph_state.values if hasattr(graph_state, "values") else {}
    if values.get("verified") and values.get("customer_id"):
        cid = str(values["customer_id"])
        name = _fetch_customer_name(cid)
        st.session_state.verified_customer = {"id": cid, "name": name}


# ── Main processing ───────────────────────────────────────────────────────────

def _process(user_input: str):
    graph = get_graph()
    config = _get_config()
    start = time.time()

    try:
        if st.session_state.waiting_for_input:
            result = graph.invoke(Command(resume=user_input), config=config)
        else:
            result = graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )

        elapsed = round(time.time() - start, 2)
        graph_state = graph.get_state(config)
        interrupt_msg = _get_interrupt_value(graph_state)
        _sync_verified_state(graph_state)

        route = (graph_state.values or {}).get("route", "music") if hasattr(graph_state, "values") else "music"

        if interrupt_msg:
            st.session_state.waiting_for_input = True
            st.session_state.interrupt_prompt = interrupt_msg
            return interrupt_msg, True, elapsed, None

        st.session_state.waiting_for_input = False
        st.session_state.interrupt_prompt = ""

        messages = result.get("messages", [])
        ai_msgs = [m for m in messages if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)]
        reply = ai_msgs[-1].content if ai_msgs else "I processed your request but have no response to display."
        return reply, False, elapsed, route

    except Exception as e:
        logger.exception("Graph error: %s", e)
        st.session_state.waiting_for_input = False
        return f"An error occurred: {e}", False, 0.0, None


# ── UI components ─────────────────────────────────────────────────────────────

def _render_sidebar():
    with st.sidebar:
        st.markdown("## 🎵 Music Store Support")

        # Verified customer card
        if st.session_state.verified_customer:
            c = st.session_state.verified_customer
            st.success(f"✅ **{c['name']}**\nCustomer ID: {c['id']}")
        else:
            st.info("🔓 Not verified\nInvoice queries will ask for your ID.")

        st.divider()

        # Quick questions — use index-based keys so they're stable across state changes
        st.markdown("#### 💡 Try asking")
        suggestions = SUGGESTIONS_VERIFIED if st.session_state.verified_customer else SUGGESTIONS_ANONYMOUS
        for i, s in enumerate(suggestions[:4]):
            if st.button(s, use_container_width=True, key=f"sug_{i}"):
                st.session_state.pending_input = s
                st.rerun()

        st.divider()

        # Session controls
        st.markdown("#### ⚙️ Session")
        st.code(f"ID: {st.session_state.thread_id[:8]}…", language=None)
        if st.button("🔄 New Conversation", use_container_width=True):
            _reset_session()
            st.rerun()

        st.divider()

        # DB health
        with st.expander("🗄️ Database Health"):
            if st.button("Run Check", use_container_width=True):
                status = verify_database()
                if status["status"] == "healthy":
                    st.success("Healthy")
                else:
                    st.warning(status["status"])
                for tbl, info in status.get("tables", {}).items():
                    icon = "✅" if info["ok"] else "❌"
                    st.caption(f"{icon} {tbl}: {info['actual']} rows")



def _render_welcome():
    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 0 1rem 0;">
            <div style="font-size:3rem;">🎵</div>
            <h3 style="margin:0.25rem 0;">Welcome to Music Store Support</h3>
            <p style="color:gray; margin:0;">
                Ask about albums, artists, and genres freely.<br>
                For invoices and purchases, I'll ask you to verify your identity.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Start with a suggestion:**")
    cols = st.columns(2)
    for i, suggestion in enumerate(SUGGESTIONS_ANONYMOUS):
        if cols[i % 2].button(suggestion, use_container_width=True, key=f"welcome_{i}"):
            st.session_state.pending_input = suggestion
            st.rerun()
    st.divider()


def _render_agent_label(route: str | None, elapsed: float):
    if route and route in AGENT_LABELS:
        icon, label, color = AGENT_LABELS[route]
        st.markdown(
            f'<span style="font-size:0.75rem; color:{color}; font-weight:600;">'
            f'{icon} {label}</span> '
            f'<span style="font-size:0.75rem; color:gray;">· ⏱ {elapsed}s</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"⏱ {elapsed}s")


def _spinner_label(waiting_for_input: bool) -> str:
    if waiting_for_input:
        return "Verifying your identity…"
    return "Thinking…"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    _init_session()
    _render_sidebar()

    st.title("🎵 Music Store Customer Support")
    st.caption("Powered by Multi-Agent AI | Chinook Digital Music Store")

    # Show welcome + suggestion grid when chat is empty
    if not st.session_state.chat_history:
        _render_welcome()

    # Render chat history
    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            if entry["role"] == "assistant" and not entry.get("is_interrupt"):
                _render_agent_label(entry.get("agent"), entry.get("elapsed", 0))

    # Verification banner
    if st.session_state.waiting_for_input:
        st.info(
            f"🔐 **Identity Verification Required**\n\n{st.session_state.interrupt_prompt}\n\n"
            "_Provide your Customer ID (1–59), email, or phone number._"
        )

    placeholder = (
        "Enter your Customer ID, email, or phone number…"
        if st.session_state.waiting_for_input
        else "Ask about music, albums, invoices, or purchases…"
    )

    # Consume a pending suggestion-chip click OR typed input
    pending = st.session_state.pop("pending_input", None)
    typed = st.chat_input(placeholder) if not pending else None
    user_input = pending or typed

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner(_spinner_label(st.session_state.waiting_for_input)):
                reply, is_interrupt, elapsed, route = _process(user_input)

            if is_interrupt:
                st.info(f"🔐 {reply}")
            else:
                st.markdown(reply)
                _render_agent_label(route, elapsed)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": reply,
            "agent": route,
            "elapsed": elapsed,
            "is_interrupt": is_interrupt,
        })
        st.rerun()


if __name__ == "__main__":
    main()
