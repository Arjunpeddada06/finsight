"""Grounded financial agent: follow-up rewriting, evidence retrieval, tool routing and cited answers."""
import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (ANSWER_SYSTEM, INSUFFICIENT_TOKEN, INVESTMENT_NOTE, REFUSAL, REWRITE_SYSTEM,
                                is_investment_advice_request)
from app.config import get_settings
from app.rag.embeddings import Embedder
from app.rag.llm import LLM, get_llm
from app.rag.retriever import SearchHit, search_chunks
from app.agents.tool_router import run_calculator, retrieve_financial_tables, wants_calculation, wants_comparison

log = logging.getLogger(__name__)
_CITE = re.compile(r"\[S(\d+)\]")


@dataclass
class SourceRef:
    label: int
    document_id: uuid.UUID
    document_name: str
    page_number: int
    section: str | None
    chunk_id: uuid.UUID
    score: float | None
    snippet: str


@dataclass
class Answer:
    text: str
    sources: list[SourceRef] = field(default_factory=list)
    refused: bool = False
    rewritten_question: str | None = None
    tool_used: str | None = None


def build_context(hits: list[SearchHit]) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        where = f"{h.document_name}, page {h.page_number}" + (f", section: {h.section}" if h.section else "")
        blocks.append(f"[S{i}] {where}\n{h.content}")
    return "\n\n---\n\n".join(blocks)


def _format_history(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"{'User' if role == 'user' else 'Assistant'}: {content[:600]}" for role, content in history)


async def rewrite_question(llm: LLM, question: str, history: list[tuple[str, str]]) -> str:
    """Turn 'What about 2024?' into a standalone question using the recent conversation."""
    if not history:
        return question
    prompt = f"Conversation:\n{_format_history(history)}\n\nFollow-up message: {question}"
    rewritten = (await llm.complete([{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": prompt}])).strip()
    rewritten = rewritten.strip('"').splitlines()[0].strip() if rewritten else ""
    return rewritten if 3 <= len(rewritten) <= 400 else question


def _refuse(rewritten: str | None) -> Answer:
    return Answer(REFUSAL, [], True, rewritten)


async def answer_question(
    session: AsyncSession,
    question: str,
    *,
    history: list[tuple[str, str]] | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int | None = None,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
) -> Answer:
    settings = get_settings()
    llm = llm or get_llm()
    history = (history or [])[-settings.history_messages:]

    standalone = await rewrite_question(llm, question, history)
    rewritten = standalone if standalone != question else None

    hits = await search_chunks(session, standalone, document_ids=document_ids, top_k=top_k or (12 if wants_comparison(standalone) else settings.retrieval_top_k), embedder=embedder)
    if not hits:
        return _refuse(rewritten)

    # Phase 8: route arithmetic requests to the deterministic calculator.
    if wants_calculation(standalone):
        evidence = [(i, hit.content) for i, hit in enumerate(hits, start=1)]
        try:
            outcome = await run_calculator(llm, standalone, evidence)
        except ValueError as exc:
            return Answer(f"I can’t calculate this reliably from the uploaded reports: {exc}", [], True, rewritten)
        selected = [n for n in outcome.citation_labels if 1 <= n <= len(hits)]
        if not selected:
            return _refuse(rewritten)
        renumber = {old: new for new, old in enumerate(dict.fromkeys(selected), start=1)}
        cited_text = re.sub(r"\[S(\d+)\]", lambda m: f"[S{renumber[int(m.group(1))]}]" if int(m.group(1)) in renumber else "", outcome.text)
        sources = [
            SourceRef(renumber[n], hits[n - 1].document_id, hits[n - 1].document_name, hits[n - 1].page_number,
                      hits[n - 1].section, hits[n - 1].chunk_id, hits[n - 1].similarity, hits[n - 1].content[:240])
            for n in dict.fromkeys(selected)
        ]
        if is_investment_advice_request(question):
            cited_text += f"\n\n{INVESTMENT_NOTE}"
        return Answer(cited_text, sources, False, rewritten, "calculator")

    # Structured table retrieval supplements the vector/keyword passages for table-heavy questions.
    table_context = ""
    tables = await retrieve_financial_tables(session, standalone, document_ids=document_ids)
    for table in tables:
        matching = next((i for i, hit in enumerate(hits, start=1)
                         if hit.document_id == table.document_id and hit.page_number == table.page_number), None)
        if matching is not None and table.markdown:
            table_context += f"\n\nTABLE DATA [S{matching}] — {table.title or table.table_type or 'Financial table'} (page {table.page_number}):\n{table.markdown}"
    user_prompt = f"SOURCES:\n\n{build_context(hits)}{table_context}\n\nQUESTION: {standalone}"
    raw = await llm.complete([{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": user_prompt}])

    if INSUFFICIENT_TOKEN in raw:
        return _refuse(rewritten)

    # Keep only citations that point at a source we really supplied; an answer with none is unsupported.
    valid = [int(n) for n in _CITE.findall(raw) if 1 <= int(n) <= len(hits)]
    if not valid:
        log.info("Answer rejected: no valid source citation")
        return _refuse(rewritten)
    cited = list(dict.fromkeys(valid))
    # Renumber citations 1..k in order of first appearance so the reader sees [1][2], not [3][7].
    renumber = {old: new for new, old in enumerate(cited, start=1)}
    text = _CITE.sub(lambda m: f"[S{renumber[int(m.group(1))]}]" if int(m.group(1)) in renumber else "", raw).strip()
    sources = [
        SourceRef(renumber[n], hits[n - 1].document_id, hits[n - 1].document_name, hits[n - 1].page_number, hits[n - 1].section,
                  hits[n - 1].chunk_id, hits[n - 1].similarity, hits[n - 1].content[:240])
        for n in cited
    ]
    if is_investment_advice_request(question):
        text = f"{text}\n\n{INVESTMENT_NOTE}"
    return Answer(text, sources, False, rewritten, "table_retrieval" if tables else "document_retrieval")
