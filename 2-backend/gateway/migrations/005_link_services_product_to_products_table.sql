-- Replace the hardcoded product enum on services.product with a real
-- foreign key against products.key, now that 004 created that table.
-- The all-or-nothing constraint (services_product_suite_all_or_nothing)
-- is unaffected and stays in place.

ALTER TABLE public.services DROP CONSTRAINT services_product_valid;

ALTER TABLE public.services
    ADD CONSTRAINT services_product_fkey
    FOREIGN KEY (product) REFERENCES public.products (key);
