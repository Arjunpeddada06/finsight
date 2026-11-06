"""Table extraction (pdfplumber) and financial-statement classification."""
import logging
import re
from dataclasses import dataclass

import pdfplumber

log = logging.getLogger(__name__)

# (table_type, keywords that must match in the table text or the page text, in priority order)
_RULES: list[tuple[str, re.Pattern]] = [
    ("income_statement", re.compile(r"profit and loss|income statement|statement of operations|profit before tax", re.I)),
    ("balance_sheet", re.compile(r"balance sheet|total assets|total equity and liabilities", re.I)),
    ("cash_flow", re.compile(r"cash flow|operating activities", re.I)),
    ("segment", re.compile(r"segment", re.I)),
    ("expenses", re.compile(r"expense", re.I)),
]


@dataclass
class ExtractedTable:
    page_number: int
    table_type: str | None
    title: str | None
    columns: list[str]
    rows: list[list[str]]
    markdown: str


def classify_table(table_text: str, title: str | None) -> str | None:
    """Table content wins; the page heading is the fallback. Whole-page text is deliberately NOT used:
    a page that merely mentions 'segment' or 'cash flow' in prose would mislabel unrelated tables."""
    for scope in (table_text, title or ""):
        for table_type, rx in _RULES:
            if rx.search(scope):
                return table_type
    return None


def _clean_cell(cell: str | None) -> str:
    return re.sub(r"\s+", " ", cell or "").strip()


def to_markdown(columns: list[str], rows: list[list[str]]) -> str:
    esc = lambda v: v.replace("|", "\\|")
    lines = ["| " + " | ".join(esc(c) for c in columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _page_title(page_text: str) -> str | None:
    for line in page_text.splitlines():
        if line.strip():
            return line.strip()[:255]
    return None


def extract_tables(path: str, page_texts: dict[int, str] | None = None) -> list[ExtractedTable]:
    """Extract every table with at least 2 rows. One bad page never fails the whole document."""
    results: list[ExtractedTable] = []
    page_texts = page_texts or {}
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            try:
                raw_tables = page.extract_tables()
            except Exception as exc:  # malformed page: skip it, keep going
                log.warning("Table extraction failed on page %s: %s", page_number, exc)
                continue
            page_text = page_texts.get(page_number) or page.extract_text() or ""
            for raw in raw_tables:
                grid = [[_clean_cell(c) for c in row] for row in raw if any(_clean_cell(c) for c in row)]
                if len(grid) < 2:
                    continue
                columns, rows = grid[0], grid[1:]
                table_text = " ".join(" ".join(r) for r in grid)
                results.append(ExtractedTable(
                    page_number=page_number,
                    table_type=classify_table(table_text, _page_title(page_text)),
                    title=_page_title(page_text),
                    columns=columns, rows=rows, markdown=to_markdown(columns, rows),
                ))
    return results
