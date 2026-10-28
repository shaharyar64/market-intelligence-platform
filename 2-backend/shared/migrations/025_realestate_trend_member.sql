-- Materialised trend membership.
--
-- Two brand endpoints answered "which of this developer's posts are in which
-- trend" by expanding jsonb_array_elements(member_posts) across every trend and
-- joining the result to realestate_intel.trend_posts - a 62k-row view that is
-- itself a union of three views, each deriving hashtags with a per-row
-- regexp_matches. /brands/{key}/trend-opportunities measured 42 seconds and
-- /trend-participation 3.5 seconds, both fired on every brand click, each
-- holding a pooled connection for the duration.
--
-- The same facts written once per run, indexed by the two columns those
-- endpoints filter on, answer in milliseconds. member_posts stays as it is -
-- this is a derived index of it, not a replacement.

CREATE TABLE IF NOT EXISTS realestate_intel.trend_member (
    run_id          text NOT NULL,
    trend_id        text NOT NULL,
    level           text NOT NULL,
    platform        text NOT NULL,
    post_id         text NOT NULL,
    author_username text,
    PRIMARY KEY (trend_id, platform, post_id)
);

CREATE INDEX IF NOT EXISTS trend_member_by_author
    ON realestate_intel.trend_member (author_username, run_id);

CREATE INDEX IF NOT EXISTS trend_member_by_run
    ON realestate_intel.trend_member (run_id, level);

-- The brand endpoints filter post_analysis on these two columns and had only
-- the (platform, post_id) primary key to work with, so every request seq
-- scanned the table and expanded jsonb on top.

CREATE INDEX IF NOT EXISTS post_analysis_by_brand
    ON realestate_intel.post_analysis (brand_key);

CREATE INDEX IF NOT EXISTS post_analysis_by_account_type
    ON realestate_intel.post_analysis (account_type);
