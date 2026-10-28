-- Adds the product-suite grouping fields used by the dashboards-ui landing
-- page, which groups services into four products (BrandIQ / CompIQ /
-- PredictIQ / GeoIQ), each split by category and country.
--
-- All three columns are nullable: a service with product IS NULL is treated
-- as ungrouped (e.g. Horeca, EV, Data Collection, Admin). Adding nullable
-- columns with no default is a metadata-only change in Postgres — no table
-- rewrite, no row-level lock, safe to run against the live table.

ALTER TABLE public.services
    ADD COLUMN product text,
    ADD COLUMN category text,
    ADD COLUMN country text;

ALTER TABLE public.services
    ADD CONSTRAINT services_product_valid
    CHECK (product IS NULL OR product IN ('brandiq', 'compiq', 'predictiq', 'geoiq'));

-- product, category, and country must be set together or not at all — the
-- frontend treats a service as ungrouped unless all three are present.
ALTER TABLE public.services
    ADD CONSTRAINT services_product_suite_all_or_nothing
    CHECK (
        (product IS NULL AND category IS NULL AND country IS NULL)
        OR (product IS NOT NULL AND category IS NOT NULL AND country IS NOT NULL)
    );
