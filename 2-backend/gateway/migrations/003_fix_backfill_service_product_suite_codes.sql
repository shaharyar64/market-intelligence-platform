-- 002_backfill_service_product_suite.sql matched services by `code`, but
-- assumed kebab-case codes (e.g. 'bank-brand-health') that don't match what's
-- actually stored (e.g. 'bank_brand_health', and 'banking'/'FOOD' for
-- bank-spatial/food-intelligence). Verified against name/route:
--   bank_brand_health    -> /bank-brand-health   (Bank Brand Health)
--   banking              -> /bank-spatial        (Banking Spatial Intelligence)
--   real_estate          -> /real-estate         (Real Estate Intelligence)
--   saudi_real_estate    -> /saudi-real-estate   (Saudi Real Estate Intelligence)
--   FOOD                 -> /food-intelligence/… (Food Intelligence)
--   trends_real_estate   -> /trends-real-estate  (Real Estate Trends)
-- 'pricing' already matched correctly in 002 — repeated here as a harmless
-- no-op re-affirmation for idempotency.
--
-- Same unconfirmed-country flags as before: real_estate and banking.

UPDATE public.services SET product = 'brandiq', category = 'Banking', country = 'Saudi Arabia'
    WHERE code = 'bank_brand_health';

UPDATE public.services SET product = 'brandiq', category = 'Real Estate', country = 'UAE'
    WHERE code = 'real_estate'; -- country unconfirmed

UPDATE public.services SET product = 'brandiq', category = 'Real Estate', country = 'Saudi Arabia'
    WHERE code = 'saudi_real_estate';

UPDATE public.services SET product = 'compiq', category = 'Pricing', country = 'UAE, Bahrain'
    WHERE code = 'pricing';

UPDATE public.services SET product = 'predictiq', category = 'F&B', country = 'Saudi Arabia'
    WHERE code = 'FOOD';

UPDATE public.services SET product = 'predictiq', category = 'Real Estate', country = 'Saudi Arabia'
    WHERE code = 'trends_real_estate';

UPDATE public.services SET product = 'geoiq', category = 'Banking', country = 'Saudi Arabia'
    WHERE code = 'banking'; -- country unconfirmed
