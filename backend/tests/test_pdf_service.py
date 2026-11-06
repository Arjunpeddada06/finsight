import pytest

from app.services.pdf_service import PDFError, clean_text, extract_pages, guess_metadata, validate_pdf
from tests.conftest import SAMPLE_PDF


def test_validate_returns_page_count():
    assert validate_pdf(str(SAMPLE_PDF)) == 8


def test_validate_rejects_corrupt_file(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\nthis is not a pdf")
    with pytest.raises(PDFError):
        validate_pdf(str(bad))


def test_page_numbers_match_pdf():
    pages = extract_pages(str(SAMPLE_PDF))
    assert [p.page_number for p in pages] == list(range(1, 9))
    assert "Statement of Profit and Loss" in pages[3].text
    assert "Balance Sheet" in pages[4].text


def test_clean_text_joins_hyphenation_and_collapses_space():
    assert clean_text("rev-\nenue   grew\n\n\n\nfast") == "revenue grew\n\nfast"


def test_guess_metadata():
    meta = guess_metadata(extract_pages(str(SAMPLE_PDF)))
    assert meta["company"] == "Meridian Industries Limited"
    assert meta["fiscal_year"] == "FY2025"
    assert meta["report_type"] == "annual"
