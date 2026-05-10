# Multi-Agent AI Customer Support — Digital Music Store

A LangGraph-powered multi-agent customer support system for a digital music store, backed by the [Chinook sample database](https://github.com/lerocha/chinook-database).

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
