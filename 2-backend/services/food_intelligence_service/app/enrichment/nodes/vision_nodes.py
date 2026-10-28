from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry, NodeFailed
from services.food_intelligence_service.app.enrichment.schema import FunctionalVisualOutput, SemioticVisualOutput

settings = get_settings()

_FUNCTIONAL_VISUAL_PROMPT = """You are a visual-content analyst for a food-industry social-listening platform.
Given ONE IMAGE from a social media post, classify what is shown using ONLY these categories:
product, ingredient, prepared_food, family, individual, in_home, out_of_home.
An image may match multiple categories (multi-label) or none.
Every category you include MUST have `visual_evidence`: a short factual description of what you
actually see supporting it (e.g. "glass jar with visible product label, no people in frame").
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
                 # image is being read for register - prepared food, in home, a
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


_SEMIOTIC_VISUAL_PROMPT = """You are a visual-content analyst for a food-industry social-listening platform.
Given ONE IMAGE from a social media post, score how strongly it visually conveys each of these axes,
0.0-1.0: premium, healthy, natural, modern, traditional, sophisticated, indulgent.
Base every score ONLY on what is visually observable, color, styling, setting, composition, props.
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
                 # image is being read for register - prepared food, in home, a
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
