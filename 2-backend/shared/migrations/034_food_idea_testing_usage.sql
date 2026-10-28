-- Token usage for Idea Testing, as reported by the provider.
--
-- idea_concepts.usage covers reading the concept (extraction).
-- idea_assessments.usage covers scoring and the evidence-search embeddings.
-- Shape: {"llm": {"<model>": {"input_tokens", "output_tokens", "total_tokens",
--         "cached_input_tokens"}}, "embeddings": {"model", "calls", "input_tokens"}}
-- Rows written before this column existed stay NULL.

ALTER TABLE food_intel.idea_concepts ADD COLUMN IF NOT EXISTS usage jsonb;

ALTER TABLE food_intel.idea_assessments ADD COLUMN IF NOT EXISTS usage jsonb;
