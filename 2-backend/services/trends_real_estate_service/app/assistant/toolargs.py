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
           "result, e.g. 'active-living-communities--all-2026'. Never the display "
           "name: 'Active Living Communities' will not match anything. If you do "
           "not have the id yet, call search_trends first.")

Quadrant = Literal["breakthrough", "slow-burner", "mainstream", "watchlist"]
# The stored platform values, not their display names: the corpus spells
# X as "twitter". Brand posts span all four; influencer posts are Instagram
# only, and community posts are Instagram and TikTok.
Platform = Literal["instagram", "tiktok", "twitter", "linkedin"]
Source = Literal["community", "brand", "influencer"]
# ISO 3166-1 alpha-2, the same codes stored in trend_posts.country.
# An enum rather than free text because the two sources spell every country
# differently - the posts say "Saudi Arabia", the account profiles say "KSA" -
# so a model writing either one by hand matched one source and silently missed
# the other. A closed list cannot be spelled wrong.
# Only Saudi Arabia and the UAE. Country reaches us from the account profile
# ("KSA" -> SA, "UAE" -> AE) and from nowhere else, so the other Gulf states
# cannot be answered for. Advertising them made the model ask for Kuwait, get
# nothing, and report that as a fact about the Kuwaiti market.
CountryCode = Literal["SA", "AE"]
PLACES = ("A place implies its country: Riyadh, Jeddah, Makkah, Madinah, Dammam, "
          "Khobar, NEOM, Diriyah and AlUla are SA; Dubai, Abu Dhabi, Sharjah, Ajman, "
          "Ras Al Khaimah, Fujairah and Umm Al Quwain are AE.")


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
        description="Country codes: SA Saudi Arabia, AE United Arab Emirates. "
                    "Those are the only two the corpus covers. Country comes "
                    "from the account profile, so it is unknown for community "
                    "posts and this narrows hard. " + PLACES)
    min_engagement: int | None = None
    hashtag: str | None = Field(
        default=None,
        description="A single hashtag, without the leading #. Matching is case-insensitive.")


class SearchTrendsArgs(BaseModel):
    query: str | None = Field(
        default=None,
        description="Property words to match against trend names, e.g. 'Dubai "
                    "Marina'. Never a quadrant name: asking for breaking-out "
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
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Country codes: SA Saudi Arabia, AE United Arab Emirates - "
                    "the only two the corpus covers. With ONE country the "
                    "results come from that market's own trend run: trends "
                    "found in that country's developer and influencer posts, "
                    "the same ones Trends Explorer shows under its Market "
                    "filter. Every result carries country. Passing both codes "
                    "is the whole market, the same as omitting this. Set it "
                    "when the user names a country or a place in one, and "
                    "never otherwise. " + PLACES)
    limit: int | None = Field(
        default=None,
        description="Omit to get the default 10. Do not set 1 to look for a single "
                    "trend - a near match would be cut.")


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


class ListBrandsArgs(BaseModel):
    limit: int | None = None
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Only developers based in these countries. Set it whenever the "
                    "question is about one country's developers: 'Saudi developers' "
                    "is ['SA'], 'UAE developers' is ['AE']. " + PLACES)


class BrandProfileArgs(BaseModel):
    brand: str = Field(description="Developer name, e.g. 'Emaar'. Partial names match.")
    limit: int | None = Field(
        default=None, description="How many of the brand's posts to aggregate.")


class BrandTrendsArgs(BaseModel):
    brand: str = Field(description="Developer name, e.g. 'Emaar'. Partial names match.")
    limit: int | None = Field(
        default=None, description="How many trends to return. Default 15.")


class DevelopersByTopicArgs(BaseModel):
    query: str = Field(
        description="The topic in concrete words developers would write in a post, "
                    "e.g. 'branded residences Armani Bvlgari Elie Saab' or 'solar net "
                    "zero LEED Estidama green building'. Not the user's sentence.")
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Only developer posts from these countries. " + PLACES)
    limit: int | None = Field(default=None, description="How many developers. Default 10.")


class DevelopersInTrendArgs(BaseModel):
    trend_id: str = Field(description=ID_HELP)
    countries: list[CountryCode] | None = Field(
        default=None,
        description="Only developers posting from these countries. Set it when the user "
                    "asked about one country's developers. " + PLACES)
    limit: int | None = Field(default=None, description="How many developers. Default 15.")


class CreateTrendArgs(BaseModel):
    query: str = Field(
        description="What the trend is about, in property words, e.g. 'branded "
                    "residences and waterfront towers'. This is the text used to retrieve "
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
        "Find property trends by name or topic. Use for questions about trends, "
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
        "'total', 'per platform' style questions about the market. It has NO "
        "developer filter: its numbers are never one developer's. For a named "
        "developer use get_brand_profile and get_brand_trends."),
    "search_posts": (
        SearchPostsArgs,
        "Find individual social posts semantically similar to a query. Use for "
        "'what are people saying', examples, or specific content."),
    "list_brands": (
        ListBrandsArgs,
        "The tracked developers, with their country and how many of their posts "
        "have been analysed. Use to answer which brands are covered, to find a "
        "country's developers, or to check a brand's spelling before calling "
        "get_brand_profile. Never decide a developer's country yourself - read it "
        "from this list."),
    "get_brand_profile": (
        BrandProfileArgs,
        "What one brand communicates: its recurring themes with evidence quotes, "
        "the offerings it features, its keywords, languages and top posts. Use for "
        "any question about a named developer's messaging, themes, offerings or "
        "communication."),
    "get_brand_trends": (
        BrandTrendsArgs,
        "Which trends a brand's own posts sit inside, with how many of its posts "
        "are in each and what share of the trend that is. This is the ONLY tool "
        "that connects a brand to trends. Use it for 'which trends does X "
        "participate in', 'where is X present', 'is X in this trend', and before "
        "any claim that a brand is or is not part of a trend - a brand profile "
        "describes messaging and says nothing about trend membership."),
    "developers_by_topic": (
        DevelopersByTopicArgs,
        "Which developers post about a topic, ranked by how many of their own posts "
        "match it, each with example posts (caption, author, URL). Use for 'which "
        "developers focus on X', 'who is doing X', 'which brands/partners do they "
        "work with' - the example captions name the partners. This is the tool for "
        "a developer-by-topic question; list_brands and get_brand_trends are not."),
    "developers_in_trend": (
        DevelopersInTrendArgs,
        "Which developers' posts sit inside one trend, with post counts, share of "
        "the trend and example posts. Use for 'which developers/brands are active "
        "in this trend'."),
    "create_trend": (
        CreateTrendArgs,
        "Build a NEW trend for a topic and save it. Use this whenever someone asks "
        "about a property topic and search_trends found no trend covering it - they do "
        "not have to ask you to 'create' anything, that judgement is yours. Always "
        "run search_trends first: if a trend already covers the topic, answer from "
        "that one instead of building a near-duplicate. The saved trend appears in "
        "the Trends Explorer marked as chat-generated and is measured and ranked "
        "exactly like the pipeline's own trends. It can come back empty: if too few "
        "posts match, nothing is created, and you must say there is not enough data "
        "on that topic rather than describing a trend that does not exist."),
}
