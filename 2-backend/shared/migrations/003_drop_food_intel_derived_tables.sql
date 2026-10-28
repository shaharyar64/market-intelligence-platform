DROP TABLE IF EXISTS food_intel.post_theme;

DROP TABLE IF EXISTS food_intel.post_product;

ALTER TABLE IF EXISTS food_intel.brand_profile
  DROP COLUMN IF EXISTS followers,
  DROP COLUMN IF EXISTS country,
  DROP COLUMN IF EXISTS industry,
  DROP COLUMN IF EXISTS is_verified;
