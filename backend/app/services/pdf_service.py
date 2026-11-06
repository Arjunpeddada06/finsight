"""PDF validation and text extraction (PyMuPDF). Page numbers are 1-based and match the PDF viewer."""
import re
from dataclasses import dataclass

import fitz  # PyMuPDF


class PDFError(Exception):
    """Raised with a user-readable message when a PDF cannot be used."""


@dataclass
class PageText:
    page_number: int
    text: str


def validate_pdf(path: str) -> int:
    """Return the page count, or raise PDFError for corrupted / encrypted / empty files."""
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PDFError("The file is not a valid or readable PDF.") from exc
    try:
        if doc.needs_pass:
            raise PDFError("The PDF is password-protected. Remove the password and upload it again.")
        if doc.page_count == 0:
            raise PDFError("The PDF has no pages.")
        return doc.page_count
    finally:
        doc.close()


_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\u00a0", " ")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _MULTI_NL.sub("\n\n", text).strip()


def extract_pages(path: str) -> list[PageText]:
    """Extract cleaned text per page. Raises PDFError if the document has no extractable text (e.g. scans)."""
    pages: list[PageText] = []
    try:
        with fitz.open(path) as doc:
            for i, page in enumerate(doc, start=1):
                pages.append(PageText(i, clean_text(page.get_text("text", sort=True))))
    except PDFError:
        raise
    except Exception as exc:
        raise PDFError("Text extraction failed. The PDF may be corrupted.") from exc
    if not any(p.text for p in pages):
        raise PDFError("No extractable text found. Scanned PDFs need OCR, which is not supported yet.")
    return pages


_YEAR = re.compile(r"(?:FY|financial year(?: ended)?[^\n\d]{0,30}?)\s?(20\d{2})", re.I)
_COMPANY = re.compile(r"^(.{3,80}?\b(?:Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?|PLC|LLC)\b)", re.I | re.M)
_TYPES = [("annual", re.compile(r"annual report", re.I)), ("quarterly", re.compile(r"quarter(?:ly)?|\bQ[1-4]\b", re.I)),
          ("earnings", re.compile(r"earnings", re.I))]


def guess_metadata(pages: list[PageText]) -> dict[str, str | None]:
    """Best-effort company / fiscal year / report type from the first pages. Always optional."""
    head = "\n".join(p.text for p in pages[:2])
    company = _COMPANY.search(head)
    year = _YEAR.search(head)
    report_type = next((name for name, rx in _TYPES if rx.search(head)), None)
    return {
        "company": company.group(1).strip() if company else None,
        "fiscal_year": f"FY{year.group(1)}" if year else None,
        "report_type": report_type,
    }
