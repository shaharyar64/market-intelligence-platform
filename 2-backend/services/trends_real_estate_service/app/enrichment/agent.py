import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from services.trends_real_estate_service.app.enrichment.nodes.grounded_nodes import (
    offering_focus_node,
    themes_node,
)
from services.trends_real_estate_service.app.enrichment.nodes.text_nodes import (
    description_node,
    keywords_node,
    semiotic_text_node,
)
from services.trends_real_estate_service.app.enrichment.nodes.vision_nodes import (
    functional_visual_node,
    semiotic_visual_node,
)
from services.trends_real_estate_service.app.enrichment.schema import (
    DescriptionOutput,
    FunctionalVisualOutput,
    KeywordsOutput,
    OfferingFocusOutput,
    SemioticTextOutput,
    SemioticVisualOutput,
    ThemesOutput,
)
from services.trends_real_estate_service.app.services.s3_media import presigned_url

logger = logging.getLogger(__name__)



class AgentState(TypedDict, total=False):
    """What the graph carries between nodes.

    A node that failed leaves its key absent, so every reader must treat these
    as optional - which is what `total=False` and the `| None` say. They were
    typed `object` before, which made every attribute access on a result
    invisible to a type checker.
    """

    caption: str
    brand_name: str
    platform: str
    description: DescriptionOutput | None
    keywords: KeywordsOutput | None
    semiotic_text: SemioticTextOutput | None
    themes: ThemesOutput | None
    offering_focus: OfferingFocusOutput | None
    _assembled: dict
    image_url: str | None
    functional_visual: FunctionalVisualOutput | None
    semiotic_visual: SemioticVisualOutput | None


def _assemble_node(state: AgentState) -> AgentState:
    description = state.get("description")
    keywords = state.get("keywords")
    semiotic_text = state.get("semiotic_text")
    themes = state.get("themes")
    offering_focus = state.get("offering_focus")
    functional_visual = state.get("functional_visual")
    semiotic_visual = state.get("semiotic_visual")

    visual_scores = semiotic_visual.scores if semiotic_visual else {}

    # Which nodes came back empty. Each node swallows its own NodeFailed and
    # yields None, so without this the assembled result of seven failed calls is
    # indistinguishable from a post that genuinely had nothing to say - and that
    # is exactly what happened under rate limiting: 6,434 posts were written as
    # valid rows of empty strings while the run reported zero errors.
    failed = [name for name, value in (
        ("description", description), ("keywords", keywords),
        ("semiotic_text", semiotic_text), ("themes", themes),
        ("offering_focus", offering_focus), ("functional_visual", functional_visual),
        ("semiotic_visual", semiotic_visual),
    ) if value is None]

    return {"_assembled": {
        "_failed_nodes": failed,
        "description": description.description if description else "",
        "language": description.language if description else None,
        "keywords": keywords.keywords if keywords else [],
        "semiotic": {
            "text": semiotic_text.semiotic_text if semiotic_text else "",
            "visual": visual_scores,
        },
        "themes": [t.model_dump() for t in themes.themes] if themes else [],
        "offering_focus": [p.model_dump() for p in offering_focus.offering_focus] if offering_focus else [],
        "functional_visual": [f.model_dump() for f in functional_visual.functional_visual] if functional_visual else [],
    }}


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("description", description_node)
    g.add_node("keywords", keywords_node)
    g.add_node("semiotic_text", semiotic_text_node)
    g.add_node("themes", themes_node)
    g.add_node("offering_focus", offering_focus_node)
    g.add_node("functional_visual", functional_visual_node)
    g.add_node("semiotic_visual", semiotic_visual_node)
    g.add_node("assemble", _assemble_node)

    all_nodes = ("description", "keywords", "semiotic_text", "themes", "offering_focus",
                 "functional_visual", "semiotic_visual")
    for node_name in all_nodes:
        g.add_edge(START, node_name)
        g.add_edge(node_name, "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def analyze_post(normalized: dict, image_key: str | None = None) -> dict:
    caption = normalized.get("text") or ""
    if not caption.strip() and not image_key:
        # Nothing to read, so nothing ran. Saying so explicitly matters: without
        # _failed_nodes this dict is indistinguishable from a clean analysis,
        # all_nodes_failed returns False, and an entirely empty row is stored
        # and then skipped forever.
        return {
            "description": "", "language": None, "keywords": [], "semiotic": {"text": "", "visual": {}},
            "themes": [], "offering_focus": [], "functional_visual": [],
            "_failed_nodes": list(ALL_NODES),
        }
    brand = normalized.get("brand") or {}
    image_url = presigned_url(image_key) if image_key else None
    result = get_graph().invoke({
        "caption": caption, "brand_name": brand.get("name", ""), "platform": normalized.get("platform", ""),
        "image_url": image_url,
    })
    return result["_assembled"]


ALL_NODES = ("description", "keywords", "semiotic_text", "themes",
             "offering_focus", "functional_visual", "semiotic_visual")


TEXT_NODES = ("description", "keywords", "semiotic_text", "themes", "offering_focus")
VISION_NODES = ("functional_visual", "semiotic_visual")


def all_nodes_failed(analysis: dict) -> bool:
    """True when no node produced anything, so the row would be empty.

    Such a post must not be stored. A written row counts as enriched and is
    skipped on the next run, which turns a transient rate limit into permanent
    missing data.
    """
    return len(analysis.get("_failed_nodes") or ()) == len(ALL_NODES)


def retryable_failures(failed: list[str], has_caption: bool, has_image: bool) -> list[str]:
    """Of the nodes that failed, the ones that could succeed if run again.

    A text node that failed on a post with no caption will fail again, and a
    vision node on a post with no image likewise - those are permanent facts
    about the post, not transient errors, and re-running them costs money for a
    guaranteed failure. Everything else is worth another attempt.

    This is what makes "already enriched" mean "already enriched successfully".
    """
    out = []
    for node in failed or ():
        if node in TEXT_NODES and not has_caption:
            continue
        if node in VISION_NODES and not has_image:
            continue
        out.append(node)
    return out
