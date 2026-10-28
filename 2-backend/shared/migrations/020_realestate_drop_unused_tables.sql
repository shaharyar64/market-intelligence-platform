-- Drop the objects nothing in this service reads.
--
-- These were built during the original Phase 1 plan, which designed a bespoke
-- data layer for real estate. That plan was superseded when we duplicated
-- food_intelligence_service instead, and the copied service consumes none of
-- them. They are orphaned by the change of direction, not by anything wrong
-- with them, and an unread table is worse than a missing one because it looks
-- like a dependency.
--
-- Verified by auditing every realestate_intel object against every .py file in
-- the service, separating reads from writes:
--
--   post_language   0 references of any kind. Cloned from food_intel by
--                   migration 016 and never wired to anything.
--   post_source     created by trend_posts_view, read by nothing. It exists so
--                   the assistant's vector search can filter by source without
--                   paying for the union - a path this service does not use.
--   taxonomy        474 rows, written by taxonomy/crosswalk.py, read by no
--                   service query. The B-over-A theme crosswalk.
--   theme_demand    3,787 rows, written by taxonomy/demand.py. Its only mention
--                   in service code is a comment saying it is not wired in.
--
-- The Google Trends bridge and the crosswalk can be rebuilt from
-- realestate.google_trends and realestate.cla whenever a consumer exists for
-- them. Nothing here is a source of record.
--
-- Superseding migrations 014 and 015, which created taxonomy and theme_demand.
-- Left in place rather than edited, so a replay from zero still runs in order.
DROP VIEW IF EXISTS realestate_intel.post_source;

DROP TABLE IF EXISTS realestate_intel.post_language;

DROP TABLE IF EXISTS realestate_intel.taxonomy;

DROP TABLE IF EXISTS realestate_intel.theme_demand;
