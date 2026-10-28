from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.retry import (
    NodeFailed,
    invoke_with_retry,
)

settings = get_settings()


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def grounded(items, caption_norm: str):
    kept, dropped = [], 0
    for item in items:
        good = [ev for ev in item.evidence if ev and _norm(ev) in caption_norm]
        if good:
            item.evidence = good
            kept.append(item)
        else:
            dropped += 1
    return kept, dropped


def make_text_node(node_name: str, schema_cls, system_prompt: str, output_key: str):
    def node(state: dict) -> dict:
        if not (state.get("caption") or "").strip():
            return {output_key: None}

        def call():
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL, temperature=settings.OPENAI_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            ).with_structured_output(schema_cls)
            messages = [SystemMessage(content=system_prompt),
                        HumanMessage(content=f'CAPTION:\n"""\n{state["caption"]}\n"""')]
            return llm.invoke(messages)

        try:
            result = invoke_with_retry(call, node_name, max_attempts=3)
            return {output_key: result}
        except NodeFailed:
            return {output_key: None}

    return node
