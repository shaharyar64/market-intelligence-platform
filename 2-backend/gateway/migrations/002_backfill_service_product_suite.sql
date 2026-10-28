-- Best-guess backfill of the new product/category/country fields from the
-- current sidebar nav labels. REVIEW WITH EACH DASHBOARD OWNER BEFORE THE
-- LANDING PAGE GOES LIVE — country is flagged unconfirmed below for
-- real-estate and bank-spatial.
--
-- digital-brand-health is left ungrouped (unclear whether it's superseded
-- by bank-brand-health/real-estate), as are the non-IQ services (horeca,
-- ev, data-collection, admin) — they simply aren't touched by this file, so
-- their product/category/country stay NULL from migration 001.
--
-- Matches rows by `code`. Any WHERE clause that doesn't match an existing
-- row is a harmless no-op — check the affected row counts when running this.

UPDATE public.services SET product = 'brandiq', category = 'Banking', country = 'Saudi Arabia'
    WHERE code = 'bank-brand-health';

UPDATE public.services SET product = 'brandiq', category = 'Real Estate', country = 'UAE'
    WHERE code = 'real-estate'; -- country unconfirmed

UPDATE public.services SET product = 'brandiq', category = 'Real Estate', country = 'Saudi Arabia'
    WHERE code = 'saudi-real-estate';

UPDATE public.services SET product = 'compiq', category = 'Pricing', country = 'UAE, Bahrain'
    WHERE code = 'pricing';

UPDATE public.services SET product = 'predictiq', category = 'F&B', country = 'Saudi Arabia'
    WHERE code = 'food-intelligence';

UPDATE public.services SET product = 'predictiq', category = 'Real Estate', country = 'Saudi Arabia'
    WHERE code = 'trends-real-estate';

UPDATE public.services SET product = 'geoiq', category = 'Banking', country = 'Saudi Arabia'
    WHERE code = 'bank-spatial'; -- country unconfirmed
