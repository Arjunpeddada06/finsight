"""Structure-aware chunking for financial reports.

Rules (see report chapter 6.2):
  * a chunk never spans two pages, so every citation has an exact page number;
  * headings start a new chunk once the current one is big enough, and are kept inside the chunk text;
  * each table becomes its own chunk(s) (header row repeated if a table must be split) and its rows are
    removed from the page text so numbers are not stored twice;
  * running headers/footers that repeat on most pages are dropped;
  * target ~800 tokens, hard maximum 1000, ~100 tokens of overlap when a long section is split by size.

Token counts are estimates (no tokenizer download needed, works offline): max(words * 1.3, chars / 4).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from app.config import get_settings
from app.services.pdf_service import PageText
from app.services.table_service import ExtractedTable

TABLE_LABELS = {
    "income_statement": "Income statement", "balance_sheet": "Balance sheet", "cash_flow": "Cash flow statement",
    "segment": "Segment performance", "expenses": "Expenses",
}


@dataclass
class ChunkConfig:
    target: int = 800
    maximum: int = 1000
    minimum: int = 80
    overlap: int = 100

    @classmethod
    def from_settings(cls) -> "ChunkConfig":
        s = get_settings()
        return cls(s.chunk_target_tokens, s.chunk_max_tokens, s.chunk_min_tokens, s.chunk_overlap_tokens)


@dataclass
class Chunk:
    page_number: int
    section: str | None
    content: str
    token_count: int
    kind: str = "text"  # "text" | "table"
    meta: dict = field(default_factory=dict)
    chunk_index: int = 0


def estimate_tokens(text: str) -> int:
    return max(int(len(text.split()) * 1.3), len(text) // 4)


# ---------------------------------------------------------------- page cleaning
def _shape(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_running_lines(pages: list[PageText]) -> list[PageText]:
    """Remove page headers/footers: lines whose shape (digits ignored) repeat on at least 40% of pages."""
    if len(pages) < 4:
        return pages
    counts: Counter[str] = Counter()
    for p in pages:
        counts.update({_shape(l) for l in p.text.splitlines() if l.strip() and len(l) <= 150})
    threshold = max(3, int(0.4 * len(pages)))
    running = {shape for shape, c in counts.items() if c >= threshold}
    return [PageText(p.page_number, "\n".join(l for l in p.text.splitlines() if _shape(l) not in running).strip()) for p in pages]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def remove_table_lines(text: str, tables: list[ExtractedTable]) -> str:
    """Drop page-text lines that are rows of an extracted table (they live in the table chunk instead)."""
    if not tables:
        return text
    rows = {_norm("".join(t.columns)) for t in tables}
    rows |= {_norm("".join(r)) for t in tables for r in t.rows}
    rows.discard("")
    return "\n".join(l for l in text.splitlines() if _norm(l) not in rows)


# ---------------------------------------------------------------- blocks
_SMALL = {"and", "of", "the", "in", "for", "to", "on", "a", "an", "or", "with", "by", "at"}
_NUMBER_PREFIX = re.compile(r"^\d+(\.\d+)*[.)]?\s+")


def is_heading(line: str, prev_closed: bool) -> bool:
    s = line.strip()
    if not prev_closed or not s or len(s) > 80 or s[-1] in ".,;:!?":
        return False
    m = _NUMBER_PREFIX.match(s)
    core = s[m.end():] if m else s  # "1.1  Introduction" is judged on "Introduction"
    if not core or not core[0].isupper() or any(c.isdigit() for c in core):
        return False
    words = core.split()
    if len(words) > 9:
        return False
    if core.isupper():
        return True
    significant = [w for w in words if w.lower() not in _SMALL]
    return bool(significant) and sum(w[0].isupper() for w in significant) >= 0.7 * len(significant)


def split_blocks(text: str) -> list[tuple[str, str]]:
    """Return [("heading"|"para", text)], merging wrapped lines into paragraphs."""
    blocks: list[tuple[str, str]] = []
    para: list[str] = []
    prev_closed = True

    def close() -> None:
        if para:
            blocks.append(("para", " ".join(para)))
            para.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s:
            close(); prev_closed = True; continue
        if is_heading(s, prev_closed):
            close(); blocks.append(("heading", s)); prev_closed = True; continue
        para.append(s)
        prev_closed = s[-1] in ".!?"
    close()
    return blocks


_SENT = re.compile(r"(?<=[.!?])\s+")


def split_oversized(text: str, cfg: ChunkConfig) -> list[str]:
    """Split a paragraph that exceeds the maximum into sentence groups of about the target size."""
    parts: list[str] = []
    cur: list[str] = []
    for sent in _SENT.split(text):
        if estimate_tokens(sent) > cfg.maximum:  # no punctuation at all: fall back to word windows
            words, step = sent.split(), max(50, int(cfg.target / 1.3))
            for i in range(0, len(words), step):
                parts.append(" ".join(words[i:i + step]))
            continue
        if cur and estimate_tokens(" ".join(cur + [sent])) > cfg.target:
            parts.append(" ".join(cur)); cur = []
        cur.append(sent)
    if cur:
        parts.append(" ".join(cur))
    return parts


def _tail(text: str, budget: int) -> str:
    """Last whole sentences of `text` totalling at most `budget` tokens (used as overlap)."""
    out: list[str] = []
    for sent in reversed(_SENT.split(text)):
        if estimate_tokens(" ".join([sent] + out)) > budget:
            break
        out.insert(0, sent)
    return " ".join(out)


# ---------------------------------------------------------------- chunk building
def _table_chunks(t: ExtractedTable, cfg: ChunkConfig) -> list[Chunk]:
    label = TABLE_LABELS.get(t.table_type or "", None) or t.title or "Table"
    head = f"Table: {label} (page {t.page_number})"
    meta = {"kind": "table", "table_type": t.table_type, "title": t.title}
    lines = t.markdown.splitlines()
    header_rows, body = lines[:2], lines[2:]
    chunks: list[Chunk] = []
    cur: list[str] = []
    for row in body:
        if cur and estimate_tokens("\n".join([head, *header_rows, *cur, row])) > cfg.maximum:
            chunks.append(_mk(t.page_number, label, "\n".join([head, *header_rows, *cur]), "table", meta)); cur = []
        cur.append(row)
    chunks.append(_mk(t.page_number, label, "\n".join([head, *header_rows, *cur]), "table", meta))
    return chunks


def _mk(page: int, section: str | None, content: str, kind: str, meta: dict | None = None) -> Chunk:
    return Chunk(page, section, content, estimate_tokens(content), kind, dict(meta or {"kind": kind}))


def build_chunks(pages: list[PageText], tables: list[ExtractedTable], cfg: ChunkConfig | None = None) -> list[Chunk]:
    cfg = cfg or ChunkConfig.from_settings()
    pages = strip_running_lines(pages)
    chunks: list[Chunk] = []
    section: str | None = None

    for page in pages:
        page_tables = [t for t in tables if t.page_number == page.page_number]
        buf: list[str] = []
        buf_section = section

        def tokens() -> int:
            return estimate_tokens("\n\n".join(buf))

        def flush(overlap: bool) -> None:
            nonlocal buf, buf_section
            text = "\n\n".join(buf).strip()
            if text:
                chunks.append(_mk(page.page_number, buf_section, text, "text"))
            carry = _tail(text, cfg.overlap) if (overlap and text) else ""
            buf = [carry] if carry else []
            buf_section = section

        for kind, text in split_blocks(remove_table_lines(page.text, page_tables)):
            if kind == "heading":
                if buf and tokens() >= cfg.minimum:
                    flush(overlap=False)
                section = text
                if not buf:
                    buf_section = section
                buf.append(text)
                continue
            pieces = split_oversized(text, cfg) if estimate_tokens(text) > cfg.maximum else [text]
            for piece in pieces:
                if buf and tokens() + estimate_tokens(piece) > cfg.target:
                    flush(overlap=True)
                buf.append(piece)
        flush(overlap=False)

        for t in page_tables:
            chunks.extend(_table_chunks(t, cfg))

    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks
