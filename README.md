# Multi-Agent AI Customer Support — Digital Music Store

A LangGraph-powered multi-agent customer support system for a digital music store, backed by the [Chinook sample database](https://github.com/lerocha/chinook-database).

## Live Demo

🚀 **[https://multi-agent-ai-customer-support.streamlit.app/](https://multi-agent-ai-customer-support.streamlit.app/)**

## Architecture

```
START → verify_info → load_memory → supervisor
                                         │
               ┌──────────┬─────────┬───┴────────┐
            music_llm  invoice_agent  (mixed:both)  reject
               │↕ ReAct
          music_tools
               │
          create_memory → END
```

### Agents

| Agent | Type | Responsibility |
|---|---|---|
| **Supervisor** | Router | Classifies intent (music/invoice/mixed/off-topic), routes queries |
| **Music Agent** | Hand-built ReAct | Albums, songs, genres, track details (5 tools) |
| **Invoice Agent** | `create_react_agent` | Invoices, purchases, support reps (4 tools) |

### Key Features

- **Identity verification** with interrupt/resume (Customer ID, email, or phone)
- **Per-customer memory** — explicit music preferences persisted across turns
- **Anti-hallucination** — 6 grounding rules enforced in every agent prompt
- **SQL injection prevention** — all queries use SQLAlchemy parameterized bindings
- **Chinook database** — loaded in-memory SQLite at startup, cached locally

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Run

```bash
PYTHONPATH=. python app.py
# Opens Streamlit at http://localhost:8501
```

Or with the venv directly:
```bash
PYTHONPATH=. /path/to/.venv/bin/streamlit run src/ui/streamlit_app.py
```

## Test

```bash
PYTHONPATH=. pytest tests/ -v
```

Expected: **28+ tests passing, 0 failures**

## Docker

```bash
docker build -t music-support .
docker run -p 8501:8501 --env-file .env music-support
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `MODEL_NAME` | ❌ | `gpt-4o-mini` | LLM model name |
| `TEMPERATURE` | ❌ | `0` | LLM temperature |
| `OPENAI_API_BASE` | ❌ | — | Custom API base URL |
| `PORT` | ❌ | `8501` | Streamlit server port |

## Sample Usage

1. Start a conversation — the system asks for your identity
2. Provide your Customer ID (e.g. `5`), email, or phone number
3. Ask music questions: *"What albums does AC/DC have?"*
4. Ask invoice questions: *"Show me my recent invoices"*
5. Ask mixed questions: *"Show my invoices and recommend similar rock songs"*
6. The system remembers preferences: *"I love jazz"* → recalled in future turns

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Customer Interface                         │
│              (Chat UI / Email / Slack / API)                      │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    INTAKE & CONTEXT LAYER                         │
│  ┌────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  Auth / CRM    │   │ Session Manager  │   │ History Loader │  │
│  │  Lookup Tool   │   │ (conversation    │   │ (past tickets) │  │
│  │                │   │  state/memory)   │   │                │  │
│  └────────────────┘   └──────────────────┘   └────────────────┘  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT (Router)                      │
│   • Classifies intent & urgency                                   │
│   • Routes to specialist agents                                   │
│   • Manages multi-turn conversation flow                          │
│   • Decides escalation vs. resolution                             │
└───┬────────┬────────┬────────┬────────┬──────────────────────────┘
    │        │        │        │        │
    ▼        ▼        ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌──────────┐
│  FAQ  │ │Billing│ │ Tech  │ │ Order │ │Escalation│
│ Agent │ │ Agent │ │Support│ │ Agent │ │  Agent   │
│       │ │       │ │ Agent │ │       │ │          │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └────┬─────┘
    │         │         │         │           │
    └─────────┴─────────┴─────────┴───────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      SHARED TOOL LAYER                            │
│  KB Search │ CRM API │ Order DB │ Ticket System │ Notifier        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                  QUALITY & FEEDBACK LAYER                         │
│    Sentiment Monitor │ QA Reviewer Agent │ Analytics Logger       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agent Inventory (7 Agents)

| Agent | Role | Key Tools |
|---|---|---|
| **Supervisor** | Intent classification, routing, flow control | CRM lookup, session state, intent classifier |
| **FAQ Agent** | General questions via RAG over knowledge base | KB vector search, product catalog |
| **Billing Agent** | Payments, invoices, subscriptions, refund eligibility | CRM API, payment gateway, refund tool |
| **Technical Support Agent** | Troubleshooting, bug reports, diagnostics | Diagnostic runner, KB search, device info lookup |
| **Order Management Agent** | Order status, returns, shipment tracking | Order DB, shipping API, return initiator |
| **Escalation Agent** | Complex/angry cases → human handoff | Ticket creator, human queue, notification sender |
| **QA / Sentiment Agent** | Monitors tone, flags risk, reviews responses | Sentiment scorer, response critic, audit logger |

---

## LangGraph State Schema

```python
class SupportState(TypedDict):
    # Conversation
    session_id: str
    customer_id: str
    messages: list[BaseMessage]

    # Routing
    intent: str                    # billing | tech | order | faq | escalate
    urgency: Literal["low", "medium", "high", "critical"]
    active_agent: str

    # Customer context
    customer_profile: dict         # from CRM
    open_tickets: list[dict]
    order_history: list[dict]

    # Resolution tracking
    resolution_status: str         # in_progress | resolved | escalated
    escalation_reason: str | None
    human_agent_id: str | None
    ticket_id: str | None

    # Quality
    sentiment_score: float         # -1.0 to 1.0
    response_approved: bool

    # Output
    final_response: str
    actions_taken: list[str]
```

---

## LangGraph Workflow

```
START
  │
  ▼
[intake_node]          ← Load CRM profile, session history, open tickets
  │
  ▼
[supervisor_node]      ← Classify intent, urgency, route decision
  │
  ├──→ [faq_node]
  ├──→ [billing_node]
  ├──→ [tech_support_node]
  ├──→ [order_node]
  └──→ [escalation_node]
           │
           ▼
     [qa_review_node]  ← Sentiment check, response quality gate
           │
    ┌──────┴──────┐
    │ approved?   │
    ▼ yes         ▼ no (revise)
[respond_node]   [supervisor_node] ← retry with feedback
    │
    ▼
[log_analytics_node]
    │
   END
```

---

## Routing Logic (Supervisor Prompt Strategy)

```
Intent Categories:
  faq         → product info, pricing, policies, how-to
  billing     → invoice, charge, subscription, payment failure
  tech        → bug, error, performance, setup, integration
  order       → status, tracking, return, refund, exchange
  escalate    → anger/frustration detected + unresolved > 2 turns
              → sensitive legal/safety topics
              → agent confidence < threshold
```

---

## Tool Definitions

```python
tools = [
    # Shared
    search_knowledge_base(query: str) -> list[Document]
    lookup_customer(customer_id: str) -> CustomerProfile
    get_open_tickets(customer_id: str) -> list[Ticket]
    create_ticket(type, priority, description, customer_id) -> Ticket

    # Billing
    get_invoice(invoice_id: str) -> Invoice
    check_refund_eligibility(order_id: str) -> RefundDecision
    initiate_refund(order_id: str, amount: float) -> RefundConfirmation

    # Technical
    run_diagnostics(account_id: str) -> DiagnosticReport
    fetch_error_logs(session_id: str) -> list[LogEntry]

    # Order
    get_order_status(order_id: str) -> OrderStatus
    track_shipment(tracking_number: str) -> ShipmentStatus
    initiate_return(order_id: str, reason: str) -> ReturnLabel

    # Escalation
    assign_human_agent(ticket_id: str, urgency: str) -> HumanAssignment
    send_notification(channel, message, recipient) -> bool

    # Quality
    score_sentiment(text: str) -> float
]
```

---

## Escalation Decision Tree

```
Customer message received
    │
    ├── sentiment_score < -0.6  ──────────────────→ ESCALATE (anger)
    │
    ├── topic in ["legal", "data breach", "threat"] → ESCALATE (sensitive)
    │
    ├── unresolved_turns > 3 AND no_progress ────→ ESCALATE (stuck)
    │
    ├── agent_confidence < 0.5 ──────────────────→ ESCALATE (uncertain)
    │
    └── otherwise ────────────────────────────→ CONTINUE specialist agent
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Orchestration | LangGraph |
| LLM | Claude claude-sonnet-4-6 (all agents) |
| Embeddings / RAG | OpenAI text-embedding-3-small + ChromaDB |
| Memory | LangGraph MemorySaver (short-term) + Redis (cross-session) |
| UI | Streamlit (chat interface + agent trace panel) |
| CRM/Order Mock | SQLite (dev) / PostgreSQL (prod) |
| Observability | LangSmith traces + custom analytics logger |

---

## Project Structure

```
customer-support-ai/
├── agents/
│   ├── supervisor.py
│   ├── faq_agent.py
│   ├── billing_agent.py
│   ├── tech_support_agent.py
│   ├── order_agent.py
│   ├── escalation_agent.py
│   └── qa_agent.py
├── tools/
│   ├── crm_tools.py
│   ├── billing_tools.py
│   ├── order_tools.py
│   ├── knowledge_base.py
│   └── notification_tools.py
├── graph/
│   ├── state.py
│   ├── workflow.py
│   └── edges.py
├── data/
│   ├── knowledge_base/        ← product docs, FAQs, policies
│   └── mock_db/               ← customers, orders, tickets
├── ui/
│   └── streamlit_app.py
├── tests/
│   └── test_scenarios.py
└── main.py
```

---

## Key Design Decisions

1. **Supervisor-as-router vs. full autonomy** — The Supervisor routes explicitly rather than letting agents self-select, giving deterministic and auditable routing.

2. **QA gate before every response** — Every agent response passes through sentiment scoring and a critic check before delivery, catching hostile or off-brand replies.

3. **Shared tool layer** — All agents call the same tool implementations, so CRM data is consistent regardless of which agent is active.

4. **Stateful multi-turn** — `SupportState` persists across all graph nodes in a session, so the Billing Agent can see that this customer already has an open tech ticket before responding.

5. **Graceful escalation** — Escalation is a first-class agent, not an afterthought, with its own handoff workflow and human queue integration.
