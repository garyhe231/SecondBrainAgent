"""
Claude-powered Q&A over the vector store.
"""
import os
from typing import List, Dict, Any, AsyncGenerator, Optional

import anthropic

from .vector_store import search

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a personal knowledge assistant — a "second brain" for the user.
You answer questions by drawing on content from their uploaded documents, notes, and media.

Guidelines:
- Always ground your answers in the retrieved context provided.
- Cite your sources by filename when referencing specific information.
- If the context doesn't contain the answer, say so honestly rather than making things up.
- Be concise but complete. Use markdown formatting for clarity.
- When multiple sources are relevant, synthesise them into a coherent answer.
"""


def build_context(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks):
        source_label = chunk["source"]
        if chunk.get("source_url"):
            source_label += f" ({chunk['source_url']})"
        parts.append(f"[{i+1}] Source: {source_label}\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


async def chat_stream(
    messages: List[Dict[str, str]],
    collection_filter: Optional[str] = None,
    tag_filter: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    messages: list of {role: 'user'|'assistant', content: str}
    The last user message is used as the search query.
    """
    query = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            query = msg["content"]
            break

    chunks = search(query, n_results=8, collection_filter=collection_filter, tag_filter=tag_filter)
    context = build_context(chunks)

    if context:
        system = SYSTEM_PROMPT + f"\n\nRelevant content from your knowledge base:\n\n{context}"
    else:
        system = SYSTEM_PROMPT + "\n\nNote: No relevant documents found in the knowledge base yet. Ask the user to upload some files."

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def get_sources_for_query(
    query: str,
    collection_filter: Optional[str] = None,
    tag_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return source chunks used for a given query (for UI display)."""
    return search(query, n_results=8, collection_filter=collection_filter, tag_filter=tag_filter)
