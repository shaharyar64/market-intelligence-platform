-- Personas are a food-vertical concept (consumer segments) with no real-estate
-- equivalent for now, so the tables come out rather than sitting empty and
-- half-wired. The assistant's pinned-persona column goes with them.
DROP TABLE IF EXISTS realestate_intel.persona_post;

DROP TABLE IF EXISTS realestate_intel.personas;

ALTER TABLE realestate_intel.assistant_conversations DROP COLUMN IF EXISTS persona;

-- The relevance verdict. food_intel called this post_food. The mechanism is the
-- same and still needed - the corpus is hashtag-scraped and carries a large
-- off-topic tail - but the column has to say what it actually decides here.
--
-- Stored rather than applied as a read-time filter so the judgement is made
-- once and every reader gets the same answer, and in its own table because it
-- is this pipeline's opinion, not a property of the community dump or the
-- developer crawl. NULL means not yet scored, which is what makes runs
-- resumable.
CREATE TABLE IF NOT EXISTS realestate_intel.post_relevance (
  platform    text NOT NULL,
  post_id     text NOT NULL,
  is_relevant boolean,
  scored_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, post_id)
);

CREATE INDEX IF NOT EXISTS ix_re_post_relevance_flag
  ON realestate_intel.post_relevance (is_relevant);

-- product_alias canonicalised food product names. Real estate resolves project
-- and offering names instead.
ALTER TABLE IF EXISTS realestate_intel.product_alias RENAME TO offering_alias;
