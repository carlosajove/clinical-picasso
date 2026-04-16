"""Chat endpoints — natural language queries."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import get_client, SCHEMA_PATH
from src.chat.query_gen import ask

router = APIRouter()


class ChatRequest(BaseModel):
    question: str


@router.post("/ask")
async def chat_ask(req: ChatRequest) -> dict:
    """Ask a natural language question about the graph."""
    client = get_client()
    result = await asyncio.to_thread(ask, req.question, client, str(SCHEMA_PATH))
    return {
        "question": result.question,
        "gq_query": result.gq_query,
        "explanation": result.explanation,
        "rows": result.rows,
        "error": result.error,
    }
