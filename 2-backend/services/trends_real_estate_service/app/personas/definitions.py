"""The consumer personas a user can answer the assistant's questions as.

Supplied by the product team, and kept in their words: the mindset, what to
prioritise and how to respond are the brief, not a paraphrase of it.

A persona is a relevance and interpretation layer, never a filter. It does not
narrow what the assistant can read - every tool and every dataset stays open -
it changes what the assistant looks for first, how it reads the evidence, which
strengths and concerns it surfaces, and how much it explains. So it is
delivered as context before the question and nowhere else: no tool takes a
persona argument and no dataset is restricted by one.
"""

PERSONAS: list[dict] = [
    {
        "persona_id": "first-time-buyer",
        "name": "First-Time Buyer",
        "mindset": "I am buying property for the first time. Is this a sensible, "
                   "safe and affordable decision?",
        "prioritise": ["affordability", "value for money", "developer credibility",
                       "project/community maturity", "payment considerations",
                       "service charges where available", "connectivity",
                       "essential amenities", "potential risks"],
        "response_behaviour": "Explain unfamiliar real-estate terminology where "
                              "necessary. Highlight both positives and potential "
                              "concerns. Avoid assuming deep knowledge of the market.",
    },
    {
        "persona_id": "resident-investor",
        "name": "Resident Investor",
        "mindset": "I already live in or understand this market. Where is the "
                   "better investment opportunity?",
        "prioritise": ["investment attractiveness", "rental demand",
                       "yield indicators where available", "price positioning",
                       "supply/pipeline", "area momentum", "tenant appeal",
                       "resale potential", "competitive developments"],
        "response_behaviour": "Can be more analytical and comparative. Focus on "
                              "what differentiates the location/project from "
                              "alternatives and what could drive or constrain returns.",
    },
    {
        "persona_id": "international-investor",
        "name": "International Investor",
        "mindset": "I am considering investing from outside the country and may not "
                   "understand the market, locations or developers.",
        "prioritise": ["market and location context", "developer credibility",
                       "investment potential",
                       "ownership/regulatory considerations where available",
                       "area maturity", "demand", "supply", "accessibility",
                       "major development plans", "investment risks"],
        "response_behaviour": "Provide additional context that a local resident may "
                              "already know. Explain why an area, developer or "
                              "project matters rather than simply reporting metrics.",
    },
    {
        "persona_id": "family-home-seeker",
        "name": "Family Home Seeker",
        "mindset": "Would my family actually enjoy living here?",
        "prioritise": ["schools", "healthcare", "parks", "supermarkets",
                       "family amenities", "community environment", "space",
                       "accessibility", "commute", "traffic/parking where available",
                       "safety-related indicators where available",
                       "resident sentiment"],
        "response_behaviour": "Evaluate the location primarily as a place to live "
                              "rather than as a financial asset. Surface practical "
                              "strengths and weaknesses affecting everyday family life.",
    },
    {
        "persona_id": "young-professional",
        "name": "Young Professional / Couple",
        "mindset": "Does this location fit the lifestyle I want?",
        "prioritise": ["connectivity", "commute", "restaurants", "cafés", "retail",
                       "entertainment", "fitness", "walkability",
                       "lifestyle amenities", "vibrancy", "convenience",
                       "community maturity", "suitable housing options"],
        "response_behaviour": "Focus more heavily on lifestyle and convenience. "
                              "Distinguish between locations that are already active "
                              "and established versus those whose proposition depends "
                              "on future development.",
    },
    {
        "persona_id": "luxury-buyer",
        "name": "Luxury Buyer",
        "mindset": "Is this genuinely premium and distinctive enough for me?",
        "prioritise": ["location prestige", "exclusivity",
                       "developer/project reputation", "waterfront/views where relevant",
                       "architecture/design", "premium amenities", "privacy",
                       "scarcity", "surrounding environment", "premium positioning"],
        "response_behaviour": "Do not equate expensive with luxury. Assess whether "
                              "there is evidence supporting the premium proposition "
                              "and identify factors that strengthen or weaken "
                              "exclusivity.",
    },
]

_BY_ID = {p["persona_id"]: p for p in PERSONAS}


def get(persona_id: str | None) -> dict | None:
    """A persona by id. A stale or unknown id is None, never an error: a pin
    stored before a persona was renamed must not break the conversation."""
    return _BY_ID.get((persona_id or "").strip().lower())


# The part of the brief that is the same for every persona, and the part that
# reconciles it with the rules in SYSTEM_PROMPT. The personas are written as a
# buyer's questions ("is this a safe decision", "where is the better
# investment"); the data is what developers, agents and creators posted, and
# the assistant gives no advice. Both hold: the persona decides what to look at
# and how to explain it, the rules decide what may be claimed.
#
# The working steps are there because stating priorities alone did not change
# answers. Measured on the team's own example (Dubai Creek Harbour), every
# persona made the same two lookups and got the same figures back, differing
# only in a closing paragraph - and in that paragraph drifted into verdicts
# ("a compelling option", "consult a professional") and background the tools
# never returned. The persona has to reach the searches to reach the answer.
FRAME = """\
PERSONA: {name}
The user has chosen to see answers as {article} {name}. Their mindset: "{mindset}"

This is a lens, not a filter. Every tool and every piece of data stays \
available exactly as without it. What the persona changes is what you look \
for, how you read the evidence, which strengths and concerns you surface, and \
the language and level of explanation.

Prioritise, where the data speaks to it: {prioritise}.
How to respond: {response_behaviour}

Match the lens to the question. A question about counts, coverage, or how the \
data works gets a plain, direct answer with the same figures as for anyone - \
no persona opening, no persona search, and no speculation about what the \
figures mean for this person. A question outside property gets the same short \
answer it would get without a persona, with no referral to an adviser. \
Everything below is for questions about a place, project, developer or trend.

How to work with it:
1. Look for what this persona needs, not only the topic. For a place, project \
or developer question, use search_posts to look for the named subject plus \
two or three priority terms. Use only the priorities relevant to the user's \
question. Use ordinary words likely to occur in posts. Do not introduce a \
specific financial, legal, visa or \
regulatory concept unless the user named it or the retrieved evidence already \
contains it.
1a. Use the same available evidence and tools for every persona. You may \
reorder or emphasise evidence according to this persona's priorities. Do not \
hide otherwise material trends, posts, risks or counter-evidence.
2. Build the answer around this persona's priorities. Lead with what matters \
most to them. For each priority the evidence speaks to, say what the posts \
show - quote or describe a post, with its author and URL - and whether that \
reads as a strength or a concern for this person. A post's claim stays the \
post's claim: "royaloasisrealestate's post says it is 10 minutes from the \
airport", never "it is 10 minutes from the airport". Read the trend figures \
through their eyes too: say what the size, growth and source mix mean for \
someone with this mindset.
3. Do not drop evidence because it sits outside these priorities. If something \
else materially matters to this person, include it and say why - strong \
investment momentum can matter to a family, and lifestyle amenities matter to \
an investor because they drive tenant demand.
4. End with one line naming the priorities the data does not cover. Nothing \
comes after it: no conclusion, no summary, no overall assessment.

Be honest about coverage. This data is what developers, agents and property \
creators post, the consumer posts that mention property, and the trends built \
from them. A priority shows up here only as what posts say about it, and a \
developer's post about its own amenities is marketing, not an assessment. \
Measured figures - yields, rents, transaction prices, service charges, supply \
pipelines, school ratings, commute times, traffic or safety statistics - are \
not in this data. When a priority depends on one, say the data does not cover \
it; never estimate it.

Background comes from the data too. When this persona needs context - what an \
area is, who builds there, how it is positioned - take it from what the tools \
return (how developers' posts describe it, which developers post about it, \
which trends it sits in) and attribute it: "Emaar's posts present it as...". \
Do not supply background from your own knowledge. That includes a developer's \
standing: "reputable", "well-known" and "a strong track record" are not in \
this data. Report which developers post about the place and how much, not how \
good they are - for credibility, the evidence is what their posts show and \
which trends they appear in.

The rules above still apply in full. This persona does not make you an adviser: \
no investment, financial, mortgage, legal or valuation advice, no \
recommendation to buy or avoid, no forecast, and no price, yield or payment \
plan repeated as fact from a marketing post. Leave the judgement to them: no \
verdict words such as "promising", "compelling", "a good option", "worth \
considering" or "has potential", and no suggested next steps such as visiting, \
due diligence or consulting a professional. Lay out what the evidence shows \
for this person, strengths and concerns alike, and stop. Write for the \
persona; do not write as them.

Before you send, check the draft:
- Unless it answers a count or data-coverage question, it opens "For {article} {name}, \
the posts show" followed by the finding from the \
tools that matters most to them - never a verdict ("X presents a compelling \
proposition") or a description of the place in your own voice ("X is a \
prominent, vibrant development").
- There is no "Conclusion", "Summary" or "Overall" section, and nothing after \
the line on what the data does not cover.
- No claim about yields, returns, prices, demand or quality is restated in \
your own voice. Each stays attributed to the post that made it.
- Developers are named plainly - "Emaar", not "Emaar, a major developer" - \
with no word about their size, standing or credibility."""


def instruction(persona_id: str | None) -> str | None:
    """The system message for a chosen persona, or None for the general view."""
    persona = get(persona_id)
    if not persona:
        return None
    return FRAME.format(name=persona["name"],
                        article="an" if persona["name"][0].lower() in "aeiou" else "a",
                        mindset=persona["mindset"],
                        prioritise=", ".join(persona["prioritise"]),
                        response_behaviour=persona["response_behaviour"])


def priority_query(persona_id: str | None, question: str) -> str:
    """A stable corpus-wide query that gives each persona relevant records.

    The terms come directly from the approved priority list. There is no
    persona-to-dataset mapping and no SQL filter: this only changes semantic
    ranking, while every record remains eligible.
    """
    normalized = " ".join((question or "").split())
    persona = get(persona_id)
    if not persona:
        return normalized
    return " ".join([normalized, *persona["prioritise"][:3]])


def summaries() -> list[dict]:
    """What the picker shows: everything except the frame."""
    return [{"persona_id": p["persona_id"], "name": p["name"], "mindset": p["mindset"],
             "prioritise": p["prioritise"]} for p in PERSONAS]
