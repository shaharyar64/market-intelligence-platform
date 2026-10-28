import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.node_factory import (
    _norm,
    grounded,
)
from services.trends_real_estate_service.app.enrichment.retry import (
    NodeFailed,
    invoke_with_retry,
)
from services.trends_real_estate_service.app.enrichment.schema import (
    OfferingFocusOutput,
    ThemesOutput,
)

settings = get_settings()
logger = logging.getLogger(__name__)

_THEMES_PROMPT = """You are a property analyst for a real-estate social-listening platform.
Given the CAPTION TEXT of one social media post, extract the PROPERTY THEMES it communicates.

WHAT COUNTS
A theme is something about the property or about living there - what it offers, where it sits,
what it looks like, who it suits, how it is bought. The test: "what would a buyer learn about
the home from this?" If the answer is nothing about the home, there is no theme.

WHAT DOES NOT COUNT
Anything about the poster or the marketing rather than the property: event promotion,
sponsorship, partnership, award, milestone, sales achievement, gratitude, greeting,
congratulation, celebration, call to action, engagement bait, announcement, brand awareness,
seasonal wishes (Ramadan, Eid, National Day, New Year). Developer names, project names and
hashtags are never themes.

Many posts in this corpus are only a greeting, an event notice or a sponsorship. Those have NO
themes - return an empty list. Do not manufacture a theme to avoid returning nothing.

HOW TO WRITE THE LABEL
Name the specific thing the caption talks about, not the area it belongs to. Write the label
you would want to see counted across thousands of posts:

    "Waterfront living"        not "Location" and not "Views and outlook"
    "Rooftop pool"             not "Amenities"
    "Payment plan"             not "Investment"
    "Smart home"               not "Smart home technology"
    "Kids' play area"          not "Children's amenities"
    "Gated community"          not "Safety and security"
    "Golf course view"         not "Views"
    "Step-free access"         not "Accessibility"

Sentence case, 1-3 English words, singular, no punctuation or emoji. The same theme must come
back with the SAME label every time or the themes cannot be counted: never "Waterfront living"
on one post and "waterfront Living" on another. Do not invent a category heading - if the only
label you can think of is a broad heading, the caption probably does not support a theme.

EVIDENCE
Every theme MUST include `evidence`: an exact phrase COPIED VERBATIM from the caption, same
characters, in the caption's original language including Arabic. If you cannot copy a phrase
that supports the theme, do not return that theme. Do not translate the evidence.

Return every theme the caption genuinely supports - a rich property post may carry four or five."""

_OFFERING_PROMPT = """You are a brand-intelligence analyst for a real-estate social-listening platform.
Given the CAPTION TEXT of one social media post, extract the specific offerings discussed - a
development or project by name, a property type, or an amenity.
Every offering MUST include `evidence`: an exact phrase COPIED VERBATIM from the caption. If you
cannot copy a supporting phrase, do not include that offering.
`offering` must be short English, lowercase and singular, even when the caption is Arabic - write
"townhouse", not "تاون هاوس" and not "Townhouse". Keep a project's own name as written: creek
harbour, damac hills, sobha hartland. `evidence` must stay in the caption's original language.
Name the thing, not the poster: a developer name, an account handle or a campaign hashtag is not an
offering. A payment plan, a handover date or a price is not an offering either - those are themes."""


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
                feedback = (f"{dropped} item(s) had evidence not found verbatim in "
                            "the caption. Only include items you can support with "
                            "an exact caption phrase.")
                retried = invoke_with_retry(lambda: call(feedback), node_name, max_attempts=3)
                retried_items = getattr(retried, list_attr)
                kept, _ = grounded(retried_items, caption_norm)

            setattr(result, list_attr, kept)
            return {output_key: result}
        except NodeFailed:
            return {output_key: None}

    return node


themes_node = _grounded_node("themes", ThemesOutput, _THEMES_PROMPT, "themes", "themes")
offering_focus_node = _grounded_node("offering_focus", OfferingFocusOutput,
                                     _OFFERING_PROMPT, "offering_focus", "offering_focus")
