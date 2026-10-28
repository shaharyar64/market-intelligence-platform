from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from services.food_intelligence_service.app.idea_testing.usage import EmbeddingCounter, run_with_usage


def test_run_with_usage_reports_provider_token_counts_per_model():
    reply = AIMessage(content="ok", response_metadata={"model_name": "gpt-4o-mini"},
                      usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150,
                                      "input_token_details": {"cache_read": 100}})
    llm = FakeMessagesListChatModel(responses=[reply])
    result, usage = run_with_usage(llm.invoke, "hello")
    assert result.content == "ok"
    assert usage == {"gpt-4o-mini": {"input_tokens": 120, "output_tokens": 30,
                                     "total_tokens": 150, "cached_input_tokens": 100}}


def test_run_with_usage_is_empty_without_llm_calls():
    assert run_with_usage(lambda: 42) == (42, {})


def test_embedding_counter_counts_calls_and_tokens():
    counter = EmbeddingCounter(lambda text: [0.0], "text-embedding-3-large")
    counter("fresh whole chicken")
    counter("bundle offer")
    assert counter.usage["model"] == "text-embedding-3-large"
    assert counter.usage["calls"] == 2
    assert counter.usage["input_tokens"] > 0


from services.food_intelligence_service.app.idea_testing.usage import with_totals

_MINI = "gpt-4o-mini-2024-07-18"


def _llm(inp, out, cached=0):
    return {_MINI: {"input_tokens": inp, "output_tokens": out,
                    "total_tokens": inp + out, "cached_input_tokens": cached}}


def test_with_totals_adds_every_step_of_a_test():
    usage = with_totals({
        "extraction": {"llm": _llm(1279, 196)},
        "scoring": {"llm": _llm(17916, 1870)},
        "embeddings": {"model": "text-embedding-3-large", "calls": 13, "input_tokens": 602},
    })
    assert usage["total_tokens"] == 1475 + 19786 + 602
    expected = ((1279 + 17916) * 0.15 + (196 + 1870) * 0.60 + 602 * 0.13) / 1e6
    assert usage["cost_usd"] == round(expected, 6)
    assert usage["scoring"]["llm"][_MINI]["input_tokens"] == 17916
    assert usage["scoring"]["llm"][_MINI]["cost_usd"] == round((17916 * 0.15 + 1870 * 0.60) / 1e6, 6)
    assert usage["extraction"]["llm"][_MINI]["cost_usd"] == round((1279 * 0.15 + 196 * 0.60) / 1e6, 6)
    assert usage["embeddings"]["total_tokens"] == 602
    assert usage["embeddings"]["cost_usd"] == round(602 * 0.13 / 1e6, 6)


def test_with_totals_prices_cached_input_at_the_cached_rate():
    usage = with_totals({"llm": _llm(1000, 0, cached=1000)})
    assert usage["cost_usd"] == round(1000 * 0.075 / 1e6, 6)


def test_with_totals_does_not_price_gpt_4o_mini_as_gpt_4o():
    assert with_totals({"llm": _llm(1_000_000, 0)})["cost_usd"] == 0.15


def test_with_totals_leaves_cost_empty_for_an_unpriced_model():
    usage = with_totals({"llm": {"some-new-model": {"input_tokens": 10, "output_tokens": 5,
                                                    "total_tokens": 15}}})
    assert usage["total_tokens"] == 15
    assert usage["cost_usd"] is None
