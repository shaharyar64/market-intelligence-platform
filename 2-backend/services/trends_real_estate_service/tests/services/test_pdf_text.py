import pytest

from services.trends_real_estate_service.app.services.pdf_text import extract_pdf_text


def test_extract_pdf_text_returns_the_full_text_by_default(monkeypatch):
    class _FakePage:
        def extract_text(self):
            return "Full document text with no cap applied."

    class _FakeReader:
        def __init__(self, *a, **k):
            self.pages = [_FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    assert extract_pdf_text(b"%PDF-1.4...") == "Full document text with no cap applied."


def test_extract_pdf_text_truncates_when_max_chars_given(monkeypatch):
    class _FakePage:
        def extract_text(self):
            return "x" * 1000

    class _FakeReader:
        def __init__(self, *a, **k):
            self.pages = [_FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    assert len(extract_pdf_text(b"%PDF-1.4...", max_chars=100)) == 100


def test_extract_pdf_text_strips_whitespace():
    import io

    from pypdf import PdfWriter
    buf = io.BytesIO()
    PdfWriter().write(buf)  # a genuinely empty PDF, no pages
    assert extract_pdf_text(buf.getvalue()) == ""


def test_extract_pdf_text_joins_multiple_pages(monkeypatch):
    class _FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, *a, **k):
            self.pages = [_FakePage("Page one."), _FakePage("Page two.")]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    assert extract_pdf_text(b"%PDF-1.4...") == "Page one.\nPage two."
