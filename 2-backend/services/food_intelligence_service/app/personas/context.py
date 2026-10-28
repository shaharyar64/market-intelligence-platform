"""Interpretive context handed to the chat model when a persona is pinned.

Deliberately separate from seeds.py. That file holds the short `definition`
prose that gets embedded to locate a persona's region of the corpus, and it must
stay short and concrete or membership changes. What is here never touches the
embedding path: it is read only at chat time, to help the model explain why a
finding matters to a segment.

The retrieved evidence still decides what is true. This text is a lens, not a
filter - the ordering is retrieved evidence first, persona context second, model
inference last.
"""

COMMON_INSTRUCTION = (
    'The user has pinned the persona "{name}" (persona_id: {persona_id}). Read '
    "every question as being about this segment unless the user plainly asks "
    "about the whole market.\n\n"
    "Use the persona context below as an interpretive lens, not as a rigid "
    "definition. Base findings primarily on the underlying retrieved data. Do "
    "not force findings to match the persona's known motivations or behaviours, "
    "and do not suppress unexpected themes because they fall outside the "
    "profile. If the data shows a new, surprising or contradictory behaviour, "
    "surface it clearly; it may represent an emerging trend.\n\n"
    "When useful, distinguish between what is observed in the data and your "
    "interpretation of why it matters for this persona. Do not pretend to be an "
    "individual consumer or say 'I' as the persona. Analyse the segment."
)

TOOL_DIRECTIVE = (
    'Pass persona="{persona_id}" to search_trends, search_posts and '
    "aggregate_posts, and say in your answer that the figures are for this "
    "persona rather than for everyone. When a question is explicitly about the "
    "whole market, drop the filter for that answer and say that you did."
)
 
LENS_RULES = (
    "How to use interpretive_context: it is a lens, not a filter, and it is not "
    "evidence. Order of authority is retrieved evidence first, persona context "
    "second, your own inference last. Do not force a finding to match the "
    "profile, and do not suppress a theme for sitting outside it. When the data "
    "contradicts the description say so directly - an emerging behaviour shows "
    "up first as a contradiction. Separate what was observed in the data from "
    "your interpretation of it. Do not write as the persona: no first person, "
    "no imagined consumer, no invented quotes."
)

PERSONA_CONTEXT: dict[str, str] = {
    "health-conscious": """\
Core orientation: Approaches food as an important contributor to long-term
wellbeing. This consumer is attentive to what goes into food and tends to
evaluate everyday choices through health, nutritional quality and prevention
rather than taste, price or convenience alone.

What tends to matter: Balanced nutrition, recognisable or credible ingredients,
lower sugar, protein, fibre, whole-food cues, natural sourcing and functional
benefits can all be relevant. Interest may extend to gut health, energy,
immunity, weight management, digestive wellbeing, vitamins/minerals and other
benefits when they feel credible and useful.

How choices are made: Often reads labels, compares nutrition panels or
ingredients, researches products and pays attention to health or wellness
information. Taste still matters strongly: a healthier product that feels like a
major compromise on enjoyment may struggle. Convenience and price matter too,
but this segment may accept some premium when the benefit is meaningful and
believable.

Key tensions: Health versus indulgence; natural/simple ingredients versus
functional fortification; aspiration to eat fresh and wholesome versus the
realities of convenient packaged food; willingness to pay for better nutrition
versus scepticism about wellness premiums and vague health claims.

Innovation lens: Generally open to new products, ingredients and formats when
there is an understandable health benefit. Scientific or expert credibility can
help unfamiliar propositions. Do not assume this segment is vegan, organic-only,
dieting, anti-processed-food or fitness obsessed.

Signals worth noticing in the data: Changing definitions of healthy, emerging
ingredients, new functional benefits, avoidance behaviours, healthier
substitutions, label scrutiny, sugar concerns, gut-health language,
better-for-you indulgence, and any unexpected food or flavour trend gaining
traction within this segment.""",

    "busy-family": """\
Core orientation: Makes food decisions for a household rather than only for the
individual. The central challenge is usually balancing family acceptance,
nutrition, convenience, trust and household economics under real time pressure.

What tends to matter: Foods that make everyday feeding easier, work across
family members, are dependable, reasonably nutritious and feel worth the money.
Familiar brands, kid-friendly products, versatile staples, suitable pack sizes,
promotions and products that reduce preparation effort can be important.

How choices are made: Purchase decisions are practical and often repetitive.
Familiarity and trust reduce risk because a failed purchase can mean wasted
money, wasted food or a meal that children will not eat. Promotions matter, but
value is broader than low price: a product that saves time, avoids waste or
works for several occasions can justify paying more.

Key tensions: Nutrition versus children's acceptance; cooking from scratch
versus time pressure; variety versus the safety of familiar favourites; quality
versus budget; individual family preferences versus the need for one workable
household solution. Parents or caregivers may aspire to healthier meals while
relying on convenient shortcuts during busy periods.

Innovation lens: New products can succeed when their usefulness is immediately
clear and the perceived risk is low. Innovation purely for novelty may be less
compelling than something that makes breakfast, lunchboxes, snacks, dinner or
entertaining easier. Trust and reassurance can be as important as excitement.

Signals worth noticing in the data: School lunchbox needs, quick meals,
convenient cooking solutions, family snacking, children's preferences,
promotions, bulk or multipacks, meal planning, food waste, affordable nutrition,
hosting and sharing occasions, and emerging behaviours that simplify household
feeding. Do not reduce this persona to 'budget shoppers' or assume all
households have young children.""",

    "food-explorer": """\
Core orientation: Treats food as a source of discovery, experience and cultural
participation. This consumer enjoys finding something new, being early to an
interesting food experience and sharing discoveries with others.

What tends to matter: New flavours, cuisines, formats, textures, combinations,
restaurants, limited editions, visually distinctive products and experiences
that feel fresh or culturally interesting. Novelty has value, but it becomes
more powerful when there is also a story, sensory payoff or social currency.

How choices are made: Discovery may come through creators, social feeds,
friends, restaurants, travel, viral recipes, new launches or culturally relevant
food moments. This segment is relatively willing to experiment and may accept a
premium for an experience that feels distinctive or worth talking about.

Key tensions: Genuine discovery versus manufactured hype; novelty versus
repeatability; visual appeal versus actual taste; being early to a trend versus
following something once it becomes mainstream. A product may generate trial
because it is unusual but fail to earn repeat purchase if the experience does
not deliver.

Innovation lens: Highly receptive to experimentation, but do not assume every
trend must be flashy, viral or Instagrammable. Quiet discovery of regional
cuisines, ingredients, techniques or combinations can be equally important. The
data should determine what is emerging rather than the persona definition
determining what counts as interesting.

Signals worth noticing in the data: New cuisines and flavour combinations,
cross-cultural food, restaurant-led trends, creator recipes, limited editions,
unusual formats and textures, aesthetic presentation, 'must try' language, new
occasions, rediscovered traditional foods and unexpected products moving from
niche discovery toward broader adoption.""",

    "fitness-focused": """\
Core orientation: Connects food choices with physical goals such as performance,
strength, recovery, body composition and disciplined nutrition. Food is often
evaluated not only as something to enjoy but also as fuel that should support a
desired outcome.

What tends to matter: Protein is frequently important, alongside calories,
sugar, carbohydrates, fats, portion size, satiety and functional benefits.
Depending on the individual and goal, interest may extend to hydration,
electrolytes, recovery, energy, supplements, meal timing and convenient foods
that fit a nutrition plan.

How choices are made: More likely than average to quantify food through macros,
calories, protein content or serving size. May meal prep, plan around training,
use protein shakes or functional products, and follow athletes, coaches or
fitness creators. However, this segment still cares about taste, convenience and
price, especially when a product is consumed frequently.

Key tensions: Performance nutrition versus everyday enjoyment; high protein
versus excess calories or sugar; disciplined eating versus indulgence;
whole-food preferences versus the convenience of supplements and packaged
functional foods; premium fitness positioning versus whether the nutritional
payoff genuinely justifies the cost.

Innovation lens: Functional credentials can gain attention quickly, but claims
need to feel meaningful. 'High protein' alone may not differentiate when many
products make the same claim. New ingredients, formats and food behaviours can
emerge beyond established gym-nutrition conventions, so do not restrict trend
discovery to protein, macros or supplements.

Signals worth noticing in the data: Protein moving into new categories,
macro-friendly substitutions, high-protein everyday foods, recovery and
hydration, meal prep, calorie efficiency, satiety, functional snacks,
performance ingredients, new attitudes toward carbohydrates/fats,
fitness-friendly indulgence, and unexpected cuisines, ingredients or formats
gaining traction among this segment.""",
}


def for_persona(persona_id: str) -> str | None:
    """The interpretive block alone, for callers that supply their own framing."""
    return PERSONA_CONTEXT.get(persona_id)


def build(name: str, persona_id: str) -> str:
    """Assemble the pinned-persona system message.

    A persona with no authored context - anything built from chat, or a new seed
    added before its context is written - still gets the common instruction and
    the tool directive, so pinning it keeps working and only the interpretive
    half is missing.
    """
    parts = [
        COMMON_INSTRUCTION.format(name=name, persona_id=persona_id),
        TOOL_DIRECTIVE.format(persona_id=persona_id),
        f"Selected persona:\nName: {name}\nID: {persona_id}",
    ]
    context = PERSONA_CONTEXT.get(persona_id)
    if context:
        parts.append(context)
    return "\n\n".join(parts)
