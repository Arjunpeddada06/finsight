from app.services.table_service import classify_table, extract_tables
from tests.conftest import SAMPLE_PDF


def test_classification_rules():
    assert classify_table("Revenue Profit before tax", None) == "income_statement"
    assert classify_table("Item FY2025", "Balance Sheet") == "balance_sheet"
    assert classify_table("Item FY2025", "Something else") is None


def test_sample_report_tables_by_page():
    by_page = {t.page_number: t for t in extract_tables(str(SAMPLE_PDF))}
    assert sorted(by_page) == [2, 3, 4, 5, 6]
    assert by_page[2].table_type is None  # highlights summary is not a financial statement
    assert by_page[3].table_type == "segment"
    assert by_page[4].table_type == "income_statement"
    assert by_page[5].table_type == "balance_sheet"
    assert by_page[6].table_type == "cash_flow"


def test_income_statement_values_are_exact():
    t = next(t for t in extract_tables(str(SAMPLE_PDF)) if t.table_type == "income_statement")
    assert t.columns == ["Particulars", "FY2025", "FY2024", "FY2023"]
    revenue = next(r for r in t.rows if r[0] == "Revenue from operations")
    assert revenue[1:] == ["12,000", "10,000", "8,500"]
    assert t.markdown.startswith("| Particulars | FY2025")
