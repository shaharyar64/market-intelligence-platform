from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.retry import (
    NodeFailed,
    invoke_with_retry,
)
from services.trends_real_estate_service.app.enrichment.schema import (
    FunctionalVisualOutput,
    SemioticVisualOutput,
)

settings = get_settings()

_FUNCTIONAL_VISUAL_PROMPT = """You are a visual-content analyst for a real-estate social-listening platform.
Given ONE IMAGE from a social media post, classify what is SHOWN using ONLY these categories:
unit_interior, exterior_facade, masterplan, amenity, view, lifestyle_scene, floorplan.

  unit_interior    rooms, finishes, fit-out, furniture, kitchens, bathrooms
  exterior_facade  the building itself, its elevation or entrance
  masterplan       aerial shot, site plan, or district-scale render
  amenity          pool, gym, park, clubhouse, retail, play area
  view             what is seen FROM the property: sea, skyline, golf, marina
  lifestyle_scene  people using the place, rather than the place alone
  floorplan        layouts, dimensions, unit mix, spec sheets

Classify the SUBJECT, not the style - how premium or minimal it looks is scored separately.
An image may match multiple categories (multi-label) or none.
Every category you include MUST have `visual_evidence`: a short factual description of what you
actually see supporting it (e.g. "furnished living room, floor-to-ceiling glass, no people in frame").
If a category is not clearly present, do not include it, do not guess."""


def _vision_llm(schema_cls):
    return ChatOpenAI(
        model=settings.OPENAI_MODEL, temperature=settings.OPENAI_TEMPERATURE, api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(schema_cls)


def functional_visual_node(state: dict) -> dict:
    image_url = state.get("image_url")
    if not image_url:
        return {"functional_visual": None}

    def call():
        messages = [
            SystemMessage(content=_FUNCTIONAL_VISUAL_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": "Classify this image."},
                {"type": "image_url",
                 # detail "low" costs ~2.9k tokens against ~25.6k for "high" on
                 # gpt-4o-mini, whose image tokeniser is unusually expensive. Both
                 # settings returned the same categories on sampled posts, and the
                 # image is being read for register - a unit interior, an amenity, a
                 # person present - not for fine detail. The high setting was 92%
                 # of the enrichment bill.
                 "image_url": {"url": image_url, "detail": "low"}},
            ]),
        ]
        return _vision_llm(FunctionalVisualOutput).invoke(messages)

    try:
        result = invoke_with_retry(call, "functional_visual", max_attempts=3)
        return {"functional_visual": result}
    except NodeFailed:
        return {"functional_visual": None}


_SEMIOTIC_VISUAL_PROMPT = """You are a visual-content analyst for a real-estate social-listening platform.
Given ONE IMAGE from a social media post, score how strongly it visually conveys each of these axes,
0.0-1.0: premium, minimalist, natural, urban, homely, bold, aspirational.

  premium      luxury materials, marble, gold, chandeliers, high finish
  minimalist   restrained palette, monochrome, uncluttered, clean lines
  natural      greenery, timber, stone, daylight, water, landscape
  urban        density, concrete, glass towers, city grid, industrial edges
  homely       warm light, soft textiles, lived-in, family-scaled
  bold         high contrast, saturated colour, dramatic angles, striking form
  aspirational status signals - cars, yachts, styled people, the life implied

Base every score ONLY on what is visually observable: colour, styling, setting, composition, props.
A render and a photograph are scored the same way, on what they show.
Omit an axis entirely if the image gives no real signal for it, do not default to a guess."""


def semiotic_visual_node(state: dict) -> dict:
    image_url = state.get("image_url")
    if not image_url:
        return {"semiotic_visual": None}

    def call():
        messages = [
            SystemMessage(content=_SEMIOTIC_VISUAL_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": "Score this image."},
                {"type": "image_url",
                 # detail "low" costs ~2.9k tokens against ~25.6k for "high" on
                 # gpt-4o-mini, whose image tokeniser is unusually expensive. Both
                 # settings returned the same categories on sampled posts, and the
                 # image is being read for register - a unit interior, an amenity, a
                 # person present - not for fine detail. The high setting was 92%
                 # of the enrichment bill.
                 "image_url": {"url": image_url, "detail": "low"}},
            ]),
        ]
        return _vision_llm(SemioticVisualOutput).invoke(messages)

    try:
        result = invoke_with_retry(call, "semiotic_visual", max_attempts=3)
        return {"semiotic_visual": result}
    except NodeFailed:
        return {"semiotic_visual": None}
