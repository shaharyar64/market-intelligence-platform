"""Step A of the brief's evaluation flow: turn raw concept input (text, an
image concept card, or a PDF concept card) into the structured fields every
downstream retrieval and scoring call uses. Never used again after this --
retrieval and scoring both read the extracted object, not the raw input, so
results stay stable across noisy phrasing.
"""
import base64

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.retry import invoke_with_retry
from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction
from services.trends_real_estate_service.app.services.pdf_text import extract_pdf_text

_PROMPT = """You are helping a real-estate brand/insight team pressure-test a concept.
Given the concept below (as typed text, an image of a concept card, or text extracted
from a PDF concept card), extract:
- need: the core consumer need or problem it addresses
- proposition: the central proposition or benefit
- claims: specific claims or reasons-to-believe actually stated
- category: the real-estate category/segment this belongs to
- audience: the target audience described or implied
- cues: important execution or visual cues (tone, imagery, format)
Use only what is actually present in the concept. Do not invent claims or cues that
are not there. A card may come with notes from the concept owner: treat them as part
of the same concept, use them to read the card correctly, and include what they add.
Capture every number stated on the card exactly as written -- prices, rates, areas,
durations, percentages, unit counts -- in claims, need, or proposition. A concept
card image may print pricing in small text easy to miss; look carefully before
concluding a number is not there."""


def _structured_llm():
    settings = get_settings()
    return ChatOpenAI(
        model=settings.OPENAI_MODEL, temperature=0.0, api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(ConceptExtraction)


_MAX_PDF_CHARS = 50_000


def _pdf_text(data: bytes) -> str:
    return extract_pdf_text(data, max_chars=_MAX_PDF_CHARS)


def extract_concept(
    raw_text: str | None = None,
    image_bytes: bytes | None = None,
    image_content_type: str | None = None,
    pdf_bytes: bytes | None = None,
) -> ConceptExtraction:
    notes = (raw_text or "").strip()
    notes_block = f"\n\nNOTES FROM THE CONCEPT OWNER ABOUT THIS CARD:\n{notes}" if notes else ""
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content_type = image_content_type or "image/png"
        human_content = [
            {"type": "image_url",
             "image_url": {"url": f"data:{content_type};base64,{b64}", "detail": "high"}},
            {"type": "text", "text": f"Extract the concept from this concept card image.{notes_block}"},
        ]
    elif pdf_bytes is not None:
        text = _pdf_text(pdf_bytes)
        if not text.strip():
            raise ValueError(
                "PDF has no extractable text (likely a scanned or image-only PDF).")
        human_content = f"CONCEPT (extracted from a PDF concept card):\n\n{text}{notes_block}"
    elif raw_text is not None:
        human_content = f"CONCEPT:\n\n{raw_text}"
    else:
        raise ValueError("extract_concept requires one of raw_text, image_bytes or pdf_bytes")

    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=human_content)]

    def call():
        return _structured_llm().invoke(messages)

    return invoke_with_retry(call, "idea_testing_extraction", max_attempts=3)
