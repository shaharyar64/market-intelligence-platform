import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry, NodeFailed
from services.food_intelligence_service.app.enrichment.node_factory import grounded, _norm
from services.food_intelligence_service.app.enrichment.schema import ThemesOutput, ProductFocusOutput

settings = get_settings()
logger = logging.getLogger(__name__)

_THEMES_PROMPT = """You are a brand-intelligence analyst for a food-industry social-listening platform.
Given the CAPTION TEXT of one social media post, extract communication themes.
Every theme MUST include `evidence`: an exact phrase COPIED VERBATIM from the caption (same
characters, including Arabic). If you cannot copy a supporting phrase, do not include that theme.
`label` should be short English; `evidence` must stay in the caption's original language."""

_PRODUCT_PROMPT = """You are a brand-intelligence analyst for a food-industry social-listening platform.
Given the CAPTION TEXT of one social media post, extract the specific products/product categories discussed.
Every product MUST include `evidence`: an exact phrase COPIED VERBATIM from the caption. If you cannot
copy a supporting phrase, do not include that product.
`product` must be short English, lowercase and singular, even when the caption is Arabic - write "milk",
not "حليب" and not "Milk". Keep the market's own word where English has no better one: laban, labneh,
kunafa. Use the most common name for the thing, so the same product is spelled the same way in every post:
"cheese", not "cheeses" or "white cheese spread"; "chicken", not "chicken pieces".
`product_ar` is the same product's common Gulf Arabic name, singular and without "ال": "حليب", "لبن", "جبنة".
`kind` is "product" for a packaged or retail food item, "ingredient" for something used to cook with, and
"dish" for a prepared meal or recipe. `evidence` must stay in the caption's original language.
Name the thing, not the poster: a brand name, an account handle or a campaign hashtag is not a product.
If one is still listed, set its `kind` to "brand" or "hashtag" so it can be left out."""


def _llm(schema_cls):
    return ChatOpenAI(
        model=settings.OPENAI_MODEL, temperature=settings.OPENAI_TEMPERATURE, api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(schema_cls)


def _grounded_node(node_name: str, schema_cls, prompt: str, list_attr: str, output_key: str):
    def node(state: dict) -> dict:
        caption = state.get("caption") or ""
        if not caption.strip():
            return {output_key: None}
        caption_norm = _norm(caption)

        def call(feedback: str | None = None):
            content = f'CAPTION:\n"""\n{caption}\n"""'
            if feedback:
                content += f"\n\nCORRECTION: {feedback}"
            messages = [SystemMessage(content=prompt), HumanMessage(content=content)]
            return _llm(schema_cls).invoke(messages)

        try:
            result = invoke_with_retry(lambda: call(), node_name, max_attempts=3)
            items = getattr(result, list_attr)
            kept, dropped = grounded(items, caption_norm)

            if dropped:
                feedback = f"{dropped} item(s) had evidence not found verbatim in the caption. Only include items you can support with an exact caption phrase."
                retried = invoke_with_retry(lambda: call(feedback), node_name, max_attempts=3)
                retried_items = getattr(retried, list_attr)
                kept, _ = grounded(retried_items, caption_norm)

            setattr(result, list_attr, kept)
            return {output_key: result}
        except NodeFailed:
            return {output_key: None}

    return node


themes_node = _grounded_node("themes", ThemesOutput, _THEMES_PROMPT, "themes", "themes")
product_focus_node = _grounded_node("product_focus", ProductFocusOutput, _PRODUCT_PROMPT, "product_focus", "product_focus")
