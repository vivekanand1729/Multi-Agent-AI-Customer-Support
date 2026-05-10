import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.prompts import OFF_TOPIC_RESPONSE, SUPERVISOR_PROMPT, VERIFIER_EXTRACTION_PROMPT
from src.config.settings import get_llm
from src.db.database import lookup_customer_by_phone, run_query_safe
from src.models.schemas import CustomerIdentifier, SupportState, SupervisorDecision
from langgraph.types import interrupt
import json

logger = logging.getLogger(__name__)


# ── Identity Verification ────────────────────────────────────────────────────

def _extract_identifier(messages: list) -> CustomerIdentifier | None:
    """Use structured LLM output to extract a customer identifier from messages."""
    human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    if not human_msgs:
        return None

    last_human = human_msgs[-1].content
    llm = get_llm()
    structured = llm.with_structured_output(CustomerIdentifier)
    prompt = [
        SystemMessage(content=VERIFIER_EXTRACTION_PROMPT),
        HumanMessage(content=last_human),
    ]
    try:
        return structured.invoke(prompt)
    except Exception as e:
        logger.error("Identifier extraction failed: %s", e)
        return None


def _lookup_customer(identifier: CustomerIdentifier) -> dict | None:
    """Look up a customer by ID, email, or phone."""
    if identifier.identifier_type == "customer_id":
        try:
            cid = int(identifier.value)
        except ValueError:
            return None
        rows = json.loads(
            run_query_safe(
                "SELECT * FROM Customer WHERE CustomerId = :cid", {"cid": cid}
            )
        )
        return rows[0] if rows else None

    if identifier.identifier_type == "email":
        rows = json.loads(
            run_query_safe(
                "SELECT * FROM Customer WHERE LOWER(Email) = LOWER(:email)",
                {"email": identifier.value},
            )
        )
        return rows[0] if rows else None

    if identifier.identifier_type == "phone":
        return lookup_customer_by_phone(identifier.value)

    return None


def verify_info_node(state: SupportState) -> dict:
    """Verify customer identity. Interrupts and asks for credentials if not found."""
    if state.get("verified"):
        logger.info("Customer already verified (id=%s), skipping", state.get("customer_id"))
        return {}

    identifier = _extract_identifier(state["messages"])

    if identifier and identifier.identifier_type != "none" and identifier.value:
        customer = _lookup_customer(identifier)
        if customer:
            cid = str(customer["CustomerId"])
            logger.info("Customer verified: id=%s", cid)
            system_msg = SystemMessage(
                content=f"SYSTEM: Verified customer_id={cid}"
            )
            return {
                "messages": [system_msg],
                "customer_id": cid,
                "verified": True,
            }

    logger.info("Verification failed — interrupting for credentials")
    new_input = interrupt(
        "I wasn't able to verify your identity. "
        "Please provide your Customer ID (a number), email address, or phone number."
    )
    return {"messages": [HumanMessage(content=new_input)]}


def route_after_verify(state: SupportState) -> str:
    if state.get("verified"):
        return "load_memory"
    return "verify_info"


# ── Supervisor ────────────────────────────────────────────────────────────────

def supervisor_node(state: SupportState) -> dict:
    """Classify the customer query and set the routing field."""
    llm = get_llm()
    structured = llm.with_structured_output(SupervisorDecision)
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + list(state["messages"])
    try:
        decision = structured.invoke(messages)
        logger.info("Supervisor decision: %s | reason: %s", decision.route, decision.reasoning)
        return {"route": decision.route}
    except Exception as e:
        logger.error("Supervisor failed: %s", e)
        return {"route": "off_topic"}


def route_supervisor(state: SupportState) -> str:
    route = state.get("route", "off_topic")
    if route == "music":
        return "music_llm"
    if route in ("invoice", "mixed"):
        return "invoice_agent"
    return "reject"


def route_after_invoice(state: SupportState) -> str:
    if state.get("route") == "mixed":
        return "music_llm"
    return "create_memory"


# ── Off-topic rejection ───────────────────────────────────────────────────────

def reject_node(state: SupportState) -> dict:
    logger.info("Rejecting off-topic query")
    return {"messages": [AIMessage(content=OFF_TOPIC_RESPONSE)]}
