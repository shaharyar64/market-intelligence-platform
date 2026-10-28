"""Step A of the brief's evaluation flow: turn raw concept input (text, an
image concept card, or a PDF concept card) into the structured fields every
downstream retrieval and scoring call uses. Never used again after this --
retrieval and scoring both read the extracted object, not the raw input, so
results stay stable across noisy phrasing.
"""
import base64

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry
from services.food_intelligence_service.app.idea_testing.schema import ConceptExtraction
from services.food_intelligence_service.app.services.pdf_text import extract_pdf_text

_PROMPT = """You are helping a food brand/insight team pressure-test a concept.
Given the concept below (as typed text, an image of a concept card, or text extracted
from a PDF concept card), extract:
- need: the core consumer need or problem it addresses
- proposition: the central proposition or benefit
- claims: specific claims or reasons-to-believe actually stated
- category: the food category/segment this belongs to
- audience: the target audience described or implied
- cues: important execution or visual cues (tone, imagery, format)
- specifics: concrete details exactly as named, one per item: brand name (also when it appears
  only in the title), flavours or ingredients, market or country, pack sizes and formats, sales
  channels, price points
Use only what is actually present in the concept. Do not invent claims or cues that
are not there. A card may come with notes from the concept owner: treat them as part
of the same concept, use them to read the card correctly, and include what they add.
Capture every number stated on the card exactly as written -- prices, rates, areas,
durations, percentages, unit counts -- in claims, need, or proposition. A concept
card image may print pricing in small text easy to miss; look carefully before
concluding a number is not there.

Also classify the input, judging from what it is actually about, not from words it
happens to mention:
- subject: what the input is about, in a few plain lowercase words (keep capitals only for
  names), e.g. "pay-per-km car insurance". For other_text, say what the text is, e.g.
  "a greeting".
- food_relation: decide from what the business is actually selling.
  - food: it sells a food or beverage product, range or brand, or campaigns for one.
  - food_adjacent: it sells something whose main job is to make, serve, deliver or store food
    or drink: a restaurant or cafe, food delivery or grocery service, kitchen appliance,
    recipe app or food packaging.
  - not_food: it sells anything else, however much it mentions food. A credit card with
    restaurant cashback sells banking, a gym with a juice bar sells fitness, a phone plan with
    free food delivery sells telecom: all not_food. When food or drink is a perk, bonus or
    add-on bundled with another product, classify by the main product.
- input_kind: concept, question or other_text. Decide this separately from food_relation:
  a question about energy is both not_food and a question.
- related_dashboard: real_estate when the subject is property or housing, food when it is
  food or food_adjacent, otherwise none.
- classification_reason: one short sentence explaining the classification.
Never bend a non-food input into a food category. When food_relation is not_food, fill
category with the input's real category."""


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
    title: str | None = None,
) -> ConceptExtraction:
    heading = f"CONCEPT TITLE: {title.strip()}\n\n" if title and title.strip() else ""
    notes = (raw_text or "").strip()
    notes_block = f"\n\nNOTES FROM THE CONCEPT OWNER ABOUT THIS CARD:\n{notes}" if notes else ""
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content_type = image_content_type or "image/png"
        human_content = [
            {"type": "image_url",
             "image_url": {"url": f"data:{content_type};base64,{b64}", "detail": "high"}},
            {"type": "text", "text": f"{heading}Extract the concept from this concept card image.{notes_block}"},
        ]
    elif pdf_bytes is not None:
        text = _pdf_text(pdf_bytes)
        if not text.strip():
            raise ValueError(
                "PDF has no extractable text (likely a scanned or image-only PDF).")
        human_content = f"{heading}CONCEPT (extracted from a PDF concept card):\n\n{text}{notes_block}"
    elif raw_text is not None:
        human_content = f"{heading}CONCEPT:\n\n{raw_text}"
    else:
        raise ValueError("extract_concept requires one of raw_text, image_bytes or pdf_bytes")

    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=human_content)]

    def call():
        return _structured_llm().invoke(messages)

    return invoke_with_retry(call, "idea_testing_extraction", max_attempts=3)
