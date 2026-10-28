ALTER TABLE food_intel.post_analysis
  ADD COLUMN IF NOT EXISTS engagement jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE food_intel.post_analysis
SET engagement = jsonb_build_object(
    'likes', COALESCE(likes, 0),
    'comments', COALESCE(comments, 0),
    'views', COALESCE(views, 0),
    'shares', COALESCE(shares, 0),
    'bookmarks', COALESCE(bookmarks, 0)
)
WHERE engagement = '{}'::jsonb;

ALTER TABLE food_intel.post_analysis
  DROP COLUMN IF EXISTS likes,
  DROP COLUMN IF EXISTS comments,
  DROP COLUMN IF EXISTS views,
  DROP COLUMN IF EXISTS shares,
  DROP COLUMN IF EXISTS bookmarks;

CREATE INDEX IF NOT EXISTS post_analysis_engagement_total_idx
  ON food_intel.post_analysis (engagement_total DESC);
