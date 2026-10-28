"""Argument schemas for the assistant's tools.

These are pydantic models rather than hand-written JSON, because LangChain
validates a pydantic `args_schema` and merely advertises a dict one. Measured:
with a raw dict schema, `quadrant="not-a-quadrant"` and `limit="twelve"` both
reached the tool body untouched - the second would have arrived at SQL as a
string. With these, the model gets a validation error back and can correct
itself, which is the behaviour the enums were there to produce in the first
place.

The descriptions are the interface. Several were written against specific
failures - the assistant searching for the word "breakthrough", or passing a
display name where a trend_id belongs - so they are load-bearing text, not
commentary.
"""
from typing import Literal

from pydantic import BaseModel, Field

ID_HELP = ("The exact `trend_id` value from a previous search_trends or get_trend "
           "result, e.g. 'dubai-chocolate-desserts--demo50k'. Never the display "
           "name: 'Dubai Chocolate Desserts' will not match anything. If you do "
           "not have the id yet, call search_trends first.")

PERSONA_HELP = ("A persona id or name from list_personas, e.g. 'health-conscious'. "
               "Restricts the answer to posts inside that persona's region of the "
               "corpus. Set this ONLY when the user is asking about a persona or "
               "segment - it discards every post outside it, so an unasked-for "
               "persona silently narrows an answer that should have been about "
               "everyone.")

Quadrant = Literal["breakthrough", "slow-burner", "mainstream", "watchlist"]
Platform = Literal["instagram", "tiktok"]
Source = Literal["community", "brand", "influencer"]
# ISO 3166-1 alpha-2, the same codes stored in community_posts.country_code.
# An enum rather than free text because the two sources spell every country
# differently - the posts say "Saudi Arabia", the account profiles say "KSA" -
# so a model writing either one by hand matched one source and silently missed
# the other. A closed list cannot be spelled wrong.
CountryCode = Literal["SA", "AE", "KW", "QA", "OM", "BH"]


class PostFilterArgs(BaseModel):
    """Filters shared by the two post tools."""

    platforms: list[Platform] | None = None
    sources: list[Source] | None = Field(
        default=None,
        description="community = consumers, brand = tracked brand accounts, "
                    "influencer = tracked creators.")
    date_from: str | None = Field(default=None, description="ISO date, inclusive")
    date_to: str | None = Field(default=None, description="ISO date, inclusive")
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Country codes: SA Saudi Arabia, AE United Arab Emirates, "
                    "KW Kuwait, QA Qatar, OM Oman, BH Bahrain. Country is "
                    "unknown for most posts, so this narrows hard.")
    min_engagement: int | None = None
    hashtag: str | None = None
    persona: str | None = Field(default=None, description=PERSONA_HELP)


class SearchTrendsArgs(BaseModel):
    query: str | None = Field(
        default=None,
        description="Food words to match against trend names, e.g. 'Dubai "
                    "chocolate'. Never a quadrant name: asking for breaking-out "
                    "trends means quadrant='breakthrough' with NO query, because "
                    "no trend is called 'breakthrough' and the text match returns "
                    "nothing.")
    quadrant: Quadrant | None = Field(
        default=None,
        description="The strategic bucket. breakthrough = small but growing fast, "
                    "slow-burner = large and growing, mainstream = large and steady, "
                    "watchlist = small and flat. Set this when the user asks for one "
                    "of those, otherwise omit it: guessing a quadrant hides every "
                    "trend in the other three.")
    level: Literal["micro", "umbrella"] | None = Field(
        default=None,
        description="Omit unless the user asked for umbrella categories.")
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Country codes: SA Saudi Arabia, AE United Arab Emirates, "
                    "KW Kuwait, QA Qatar, OM Oman, BH Bahrain. Ranks trends by "
                    "the share of their posts from those countries. Country is "
                    "unknown for most posts, so every result also carries "
                    "country_coverage_pct - how much of the trend could be "
                    "placed at all. Set this ONLY when the user names a country.")
    limit: int | None = Field(
        default=None,
        description="Omit to get the default 10. Do not set 1 to look for a single "
                    "trend - a near match would be cut.")
    persona: str | None = Field(
        default=None,
        description="Rank trends by how much of each one belongs to this persona, "
                    "instead of by size. Use for 'which trends matter to X'. "
                    + PERSONA_HELP)


class TrendIdArgs(BaseModel):
    trend_id: str = Field(description=ID_HELP)


class CompareTrendsArgs(BaseModel):
    trend_ids: list[str] = Field(description=ID_HELP)


class AggregatePostsArgs(PostFilterArgs):
    group_by: Literal["platform", "source", "country", "month"] | None = None
    metric: Literal["count", "likes", "engagement", "views"] | None = None


class SearchPostsArgs(PostFilterArgs):
    query: str
    limit: int | None = None


class ListPersonasArgs(BaseModel):
    """No arguments: there are a handful of personas and the list is the answer."""


class PersonaIdArgs(BaseModel):
    persona_id: str = Field(description=PERSONA_HELP)


class ListBrandsArgs(BaseModel):
    limit: int | None = None


class BrandProfileArgs(BaseModel):
    brand: str = Field(description="Brand name, e.g. 'Almarai'. Partial names match.")
    limit: int | None = Field(
        default=None, description="How many of the brand's posts to aggregate.")


class BrandTrendsArgs(BaseModel):
    brand: str = Field(description="Brand name, e.g. 'Almarai'. Partial names match.")
    limit: int | None = Field(
        default=None, description="How many trends to return. Default 15.")


class CreateTrendArgs(BaseModel):
    query: str = Field(
        description="What the trend is about, in food words, e.g. 'matcha lattes "
                    "and specialty coffee'. This is the text used to retrieve "
                    "posts, so describe the subject, not the request: 'make me a "
                    "trend' retrieves nothing.")
    name: str | None = Field(
        default=None,
        description="Display name for the trend. Omit to use the query itself.")


# name -> (args model, description). The description is what the model reads to
# decide whether a tool applies, so it stays beside the arguments it governs.
TOOL_ARGS: dict[str, tuple[type[BaseModel], str]] = {
    "search_trends": (
        SearchTrendsArgs,
        "Find food trends by name or topic. Use for questions about trends, "
        "rankings, what is growing, or what territories exist. Send `query` alone "
        "unless the user asked for a filter: every other argument NARROWS the "
        "search and can hide the trend being asked about."),
    "get_trend": (
        TrendIdArgs,
        "Full detail for one trend: metrics, weekly timeline, source mix and "
        "example posts."),
    "compare_trends": (
        CompareTrendsArgs,
        "Compare headline metrics for two or more trends."),
    "get_timeline": (
        TrendIdArgs,
        "Weekly post counts, engagement and creators for one trend."),
    "aggregate_posts": (
        AggregatePostsArgs,
        "Counts and sums across posts, grouped by a dimension. Use for 'how many', "
        "'total', 'per platform' style questions."),
    "search_posts": (
        SearchPostsArgs,
        "Find individual social posts semantically similar to a query. Use for "
        "'what are people saying', examples, or specific content."),
    "list_brands": (
        ListBrandsArgs,
        "The tracked food brands, with how many of their posts have been analysed. "
        "Use to answer which brands are covered, or to check a brand's spelling "
        "before calling get_brand_profile."),
    "get_brand_profile": (
        BrandProfileArgs,
        "What one brand communicates: its recurring themes with evidence quotes, "
        "the products it features, its keywords, languages and top posts. Use for "
        "any question about a named brand's messaging, themes, products or "
        "communication."),
    "get_brand_trends": (
        BrandTrendsArgs,
        "Which trends a brand's own posts sit inside, with how many of its posts "
        "are in each and what share of the trend that is. This is the ONLY tool "
        "that connects a brand to trends. Use it for 'which trends does X "
        "participate in', 'where is X present', 'is X in this trend', and before "
        "any claim that a brand is or is not part of a trend - a brand profile "
        "describes messaging and says nothing about trend membership."),
    "list_personas": (
        ListPersonasArgs,
        "The consumer personas being tracked, with how many posts each one covers. "
        "Call this before using a `persona` argument, and whenever the user asks "
        "who the personas or segments are."),
    "get_persona": (
        PersonaIdArgs,
        "One persona in full: the segment definition the client gave us, and "
        "separately what the corpus shows about it - post and author counts, "
        "where those posts come from, the trends it is concentrated in, its "
        "hashtags, its visual profile and real example posts. Use for any "
        "question about what a persona cares about, what is growing for them, or "
        "which trends are theirs. Keep the two apart when you answer: the "
        "definition is what the client believes, the measurements are what the "
        "posts show."),
    "create_trend": (
        CreateTrendArgs,
        "Build a NEW trend for a topic and save it. Use this whenever someone asks "
        "about a food topic and search_trends found no trend covering it - they do "
        "not have to ask you to 'create' anything, that judgement is yours. Always "
        "run search_trends first: if a trend already covers the topic, answer from "
        "that one instead of building a near-duplicate. The saved trend appears in "
        "the Trends Explorer marked as chat-generated and is measured and ranked "
        "exactly like the pipeline's own trends. It can come back empty: if too few "
        "posts match, nothing is created, and you must say there is not enough data "
        "on that topic rather than describing a trend that does not exist."),
}
