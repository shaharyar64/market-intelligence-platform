-- Run only after the code that no longer reads product_alias is deployed.
-- Product names and their Arabic labels now come from post_analysis
-- (product_focus items carry product, product_ar and kind).

DROP TABLE IF EXISTS food_intel.product_alias;
