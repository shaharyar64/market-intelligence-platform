from services.trends_real_estate_service.app.enrichment.node_factory import (
    make_text_node,
)
from services.trends_real_estate_service.app.enrichment.schema import (
    DescriptionOutput,
    KeywordsOutput,
    SemioticTextOutput,
)

_DESCRIPTION_PROMPT = """You are a brand-intelligence analyst for a real-estate social-listening platform.
Given the CAPTION TEXT of one social media post, write a neutral 1-2 sentence summary of what it says,
and identify the caption's dominant language as an ISO 639-1 code (use 'mixed' only if genuinely both).
Use ONLY the caption. Do not invent facts, do not comment on engagement or performance."""

_KEYWORDS_PROMPT = """You are a brand-intelligence analyst for a real-estate social-listening platform.
Given the CAPTION TEXT of one social media post, extract the salient keywords/hashtags that are
ACTUALLY PRESENT in the caption. Do not invent keywords that aren't there. If none, return an empty list."""

_SEMIOTIC_TEXT_PROMPT = """You are a brand-intelligence analyst for a real-estate social-listening platform.
Given the CAPTION TEXT of one social media post, give a brief reading of the tone and cultural
cues conveyed by the WORDING ONLY (not the property itself). If nothing is determinable, return an
empty string -- do not guess."""

description_node = make_text_node("description", DescriptionOutput, _DESCRIPTION_PROMPT, "description")
keywords_node = make_text_node("keywords", KeywordsOutput, _KEYWORDS_PROMPT, "keywords")
semiotic_text_node = make_text_node("semiotic_text", SemioticTextOutput, _SEMIOTIC_TEXT_PROMPT, "semiotic_text")
