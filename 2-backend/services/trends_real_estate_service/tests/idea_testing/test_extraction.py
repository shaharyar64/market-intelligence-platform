from unittest.mock import MagicMock, patch

import pytest

from services.trends_real_estate_service.app.idea_testing import extraction
from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction

_STUB = ConceptExtraction(
    need="need", proposition="prop", claims=["c1"], category="cat",
    audience="aud", cues=["cue"],
)


def test_extract_concept_from_text_invokes_the_llm_with_the_text():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        result = extraction.extract_concept(raw_text="A milestone-linked payment plan.")
    assert result == _STUB
    messages = fake_llm.invoke.call_args[0][0]
    assert "milestone-linked" in messages[1].content


def test_extract_concept_from_image_sends_a_vision_content_block():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        result = extraction.extract_concept(image_bytes=b"\x89PNG...", image_content_type="image/png")
    assert result == _STUB
    messages = fake_llm.invoke.call_args[0][0]
    blocks = messages[1].content
    assert any(b.get("type") == "image_url" for b in blocks)
    assert blocks[0]["type"] == "image_url"
    assert blocks[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_extract_concept_from_pdf_extracts_text_first(monkeypatch):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    monkeypatch.setattr(extraction, "_pdf_text", lambda data: "Extracted PDF concept text")
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        result = extraction.extract_concept(pdf_bytes=b"%PDF-1.4...")
    assert result == _STUB
    messages = fake_llm.invoke.call_args[0][0]
    assert "Extracted PDF concept text" in messages[1].content


def test_extract_concept_from_image_requests_high_detail_vision():
    # "auto" detail lets the model downscale the image before reading it,
    # which is how a real test lost a price ("AED 150/hour") printed on a
    # concept card. "high" forces full-resolution tiles.
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        extraction.extract_concept(image_bytes=b"\x89PNG...", image_content_type="image/png")
    blocks = fake_llm.invoke.call_args[0][0][1].content
    assert blocks[0]["image_url"]["detail"] == "high"


def test_extract_concept_prompt_requires_every_number_to_be_captured():
    assert "number" in extraction._PROMPT.lower() or "price" in extraction._PROMPT.lower()


def test_extract_concept_from_image_includes_optional_owner_notes():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        extraction.extract_concept(raw_text="Launch price is AED 1.2M for 1BR units.",
                                   image_bytes=b"\x89PNG...", image_content_type="image/png")
    blocks = fake_llm.invoke.call_args[0][0][1].content
    assert blocks[0]["type"] == "image_url"
    assert "Launch price is AED 1.2M" in blocks[1]["text"]


def test_extract_concept_from_image_without_notes_sends_only_the_card_instruction():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        extraction.extract_concept(raw_text="   ", image_bytes=b"\x89PNG...", image_content_type="image/png")
    text = fake_llm.invoke.call_args[0][0][1].content[1]["text"]
    assert "notes" not in text.lower()


def test_extract_concept_from_pdf_includes_optional_owner_notes(monkeypatch):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB
    monkeypatch.setattr(extraction, "_pdf_text", lambda data: "Extracted PDF concept text")
    with patch.object(extraction, "_structured_llm", return_value=fake_llm):
        extraction.extract_concept(raw_text="Targets GCC families relocating to Dubai.",
                                   pdf_bytes=b"%PDF-1.4...")
    content = fake_llm.invoke.call_args[0][0][1].content
    assert "Extracted PDF concept text" in content
    assert "Targets GCC families relocating to Dubai." in content


def test_extract_concept_requires_one_input():
    with pytest.raises(ValueError):
        extraction.extract_concept()


def test_extract_concept_from_pdf_rejects_empty_extracted_text(monkeypatch):
    monkeypatch.setattr(extraction, "_pdf_text", lambda data: "")
    with pytest.raises(ValueError):
        extraction.extract_concept(pdf_bytes=b"%PDF-1.4...")


def test_extract_concept_from_pdf_rejects_whitespace_only_extracted_text(monkeypatch):
    monkeypatch.setattr(extraction, "_pdf_text", lambda data: "   \n\t  ")
    with pytest.raises(ValueError):
        extraction.extract_concept(pdf_bytes=b"%PDF-1.4...")


def test_pdf_text_truncates_very_long_output(monkeypatch):
    class _FakePage:
        def extract_text(self):
            return "x" * (extraction._MAX_PDF_CHARS * 2)

    class _FakeReader:
        def __init__(self, *a, **k):
            self.pages = [_FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    text = extraction._pdf_text(b"%PDF-1.4...")
    assert len(text) == extraction._MAX_PDF_CHARS
