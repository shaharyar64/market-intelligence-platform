-- New Product resource so admins can add/rename/reorder main categories
-- (BrandIQ / CompIQ / PredictIQ / GeoIQ today) without a code deploy on
-- either end. See gateway/app/api/admin.py's /admin/products endpoints.

CREATE TABLE public.products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key text NOT NULL UNIQUE,       -- slug, immutable once created (e.g. "brandiq")
    label text NOT NULL,            -- display name (e.g. "BrandIQ")
    tagline text,
    icon text,
    color text,                     -- hex or named token; frontend adapts
    sort_order integer NOT NULL DEFAULT 0,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the four products that exist today as a hardcoded enum/array on both
-- ends. label/tagline/icon/color below are placeholders — dashboards-ui's
-- lib/productGroups.ts PRODUCTS array has the real current values; sync
-- those in (via PATCH /admin/products) before cutting the frontend over.
INSERT INTO public.products (key, label, sort_order) VALUES
    ('brandiq', 'BrandIQ', 0),
    ('compiq', 'CompIQ', 1),
    ('predictiq', 'PredictIQ', 2),
    ('geoiq', 'GeoIQ', 3);
