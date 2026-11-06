from app.rag.chunking import (ChunkConfig, build_chunks, estimate_tokens, is_heading, remove_table_lines,
                              split_blocks, strip_running_lines)
from app.services.pdf_service import PageText, extract_pages
from app.services.table_service import ExtractedTable, extract_tables
from tests.conftest import SAMPLE_PDF


def _sample():
    pages = extract_pages(str(SAMPLE_PDF))
    return pages, extract_tables(str(SAMPLE_PDF), {p.page_number: p.text for p in pages})


def test_heading_detection():
    assert is_heading("Financial Highlights", True)
    assert is_heading("RISK FACTORS", True)
    assert is_heading("1.1  Introduction to Finance", True)
    assert not is_heading("Revenue growth was strong.", True)           # sentence
    assert not is_heading("Revenue from operations 12,000 10,000", True)  # table row (digits)
    assert not is_heading("Financial Highlights", False)                # mid-paragraph line


def test_blocks_merge_wrapped_lines():
    blocks = split_blocks("Risk Factors\n\nFirst line of a\nwrapped paragraph.\n\nSecond paragraph.")
    assert blocks == [("heading", "Risk Factors"), ("para", "First line of a wrapped paragraph."), ("para", "Second paragraph.")]


def test_running_footer_removed_but_only_for_longer_documents():
    pages = [PageText(i, f"Body {i}\nCompany Ltd - Report Page {i}") for i in range(1, 6)]
    assert all("Company Ltd" not in p.text for p in strip_running_lines(pages))
    short = pages[:3]
    assert strip_running_lines(short) == short


def test_table_rows_removed_from_text():
    t = ExtractedTable(2, None, "T", ["Item", "FY2025"], [["Revenue", "12,000"]], "")
    assert remove_table_lines("Intro line\nItem FY2025\nRevenue 12,000\nOutro", [t]) == "Intro line\nOutro"


def test_sample_report_chunks_have_correct_pages_and_types():
    chunks = build_chunks(*_sample())
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    tables = [c for c in chunks if c.kind == "table"]
    assert sorted(c.page_number for c in tables) == [2, 3, 4, 5, 6]
    income = next(c for c in tables if c.page_number == 4)
    assert income.section == "Income statement" and "| Revenue from operations | 12,000 | 10,000 | 8,500 |" in income.content
    assert any(c.section == "Risk Factors" and c.page_number == 7 for c in chunks)


def test_no_table_numbers_duplicated_in_text_chunks_and_no_footer():
    chunks = build_chunks(*_sample())
    text = " ".join(c.content for c in chunks if c.kind == "text")
    assert "Revenue from operations 12,000" not in text
    assert "SAMPLE / FICTIONAL DATA) Page" not in text


def test_chunks_never_exceed_maximum_and_overlap_is_applied():
    para = " ".join(f"Sentence number {i} explains the company performance in detail." for i in range(400))
    cfg = ChunkConfig(target=200, maximum=300, minimum=50, overlap=40)
    chunks = build_chunks([PageText(1, "Overview\n\n" + para)], [], cfg)
    assert len(chunks) > 3
    assert all(c.token_count <= cfg.maximum for c in chunks)
    assert all(c.page_number == 1 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):  # overlap: the next chunk starts with the end of the previous one
        last_sentence = prev.content.split(". ")[-1].strip()
        assert last_sentence[:30] in nxt.content


def test_oversized_table_is_split_with_header_repeated():
    rows = [[f"Item {i}", "1,000", "2,000"] for i in range(300)]
    md = "| Item | FY2025 | FY2024 |\n|---|---|---|\n" + "\n".join(f"| {r[0]} | {r[1]} | {r[2]} |" for r in rows)
    t = ExtractedTable(4, "expenses", "Expenses", ["Item", "FY2025", "FY2024"], rows, md)
    chunks = build_chunks([PageText(4, "Expenses")], [t], ChunkConfig(maximum=400))
    tables = [c for c in chunks if c.kind == "table"]
    assert len(tables) > 1 and all("| Item | FY2025 | FY2024 |" in c.content for c in tables)
    assert all(c.token_count <= 400 + 30 for c in tables)


def test_token_estimate_is_reasonable():
    assert estimate_tokens("") == 0
    assert 100 <= estimate_tokens("word " * 100) <= 200
