from typing import Annotated, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class CustomerIdentifier(BaseModel):
    """Structured extraction of a customer identifier from a message."""

    identifier_type: Literal["customer_id", "email", "phone", "none"]
    value: str = ""


class UserProfile(BaseModel):
    """Per-customer preference profile stored in InMemoryStore."""

    customer_id: str
    music_preferences: List[str] = []


class MemoryExtraction(BaseModel):
    """Explicit music preferences extracted from the conversation.

    Only extract from explicit statements like 'I love rock' or 'AC/DC is my favourite'.
    Never extract from questions like 'Do you have jazz?' or 'What rock albums exist?'.
    If no explicit preference is stated, return an empty list.
    """

    music_preferences: List[str]


class SupervisorDecision(BaseModel):
    """Supervisor routing decision."""

    route: Literal["music", "invoice", "mixed", "off_topic"]
    reasoning: str


class SupportState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    customer_id: Optional[str]
    verified: bool
    loaded_memory: str
    route: str
