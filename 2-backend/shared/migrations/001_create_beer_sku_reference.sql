-- Beer SKU reference table: canonical brand/format/category combinations
CREATE TABLE IF NOT EXISTS beer_pricing_analysis.beer_sku_reference (
    id          SERIAL PRIMARY KEY,
    brand       TEXT        NOT NULL,
    pack_type   TEXT        NOT NULL,
    pack_size   TEXT        NOT NULL,
    pack        INTEGER     NOT NULL,
    sub_type    TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (brand, pack_type, pack_size, pack, sub_type)
);

-- ── PREMIUM ──────────────────────────────────────────────────────────────────
INSERT INTO beer_pricing_analysis.beer_sku_reference (brand, pack_type, pack_size, pack, sub_type, category) VALUES
  ('Heineken',  'Can',   '33cl',   24, 'regular', 'premium'),
  ('Heineken',  'Can',   '50cl',   24, 'regular', 'premium'),
  ('Heineken',  'Glass', '33cl',   24, 'regular', 'premium'),
  ('Corona',    'Can',   '35.5cl', 24, 'regular', 'premium'),
  ('Corona',    'Glass', '35.5cl', 24, 'regular', 'premium'),
  ('Stella',    'Can',   '33cl',   24, 'regular', 'premium'),
  ('Stella',    'Glass', '33cl',   24, 'regular', 'premium')
ON CONFLICT DO NOTHING;

-- ── SUPER PREMIUM ─────────────────────────────────────────────────────────────
INSERT INTO beer_pricing_analysis.beer_sku_reference (brand, pack_type, pack_size, pack, sub_type, category) VALUES
  ('Birra Moretti', 'Can',   '33cl', 24, 'regular', 'super_premium'),
  ('Birra Moretti', 'Can',   '50cl', 24, 'regular', 'super_premium'),
  ('Birra Moretti', 'Glass', '33cl', 24, 'regular', 'super_premium'),
  ('Peroni',        'Can',   '35.5cl', 24, 'regular', 'super_premium'),
  ('Peroni',        'Glass', '33cl',   24, 'regular', 'super_premium')
ON CONFLICT DO NOTHING;

-- ── MAINSTREAM ────────────────────────────────────────────────────────────────
INSERT INTO beer_pricing_analysis.beer_sku_reference (brand, pack_type, pack_size, pack, sub_type, category) VALUES
  ('Amstel',    'Can',   '35.5cl', 24, 'light',   'mainstream'),
  ('Amstel',    'Glass', '35.5cl', 24, 'light',   'mainstream'),
  ('Amstel',    'Can',   '33cl',   24, 'regular', 'mainstream'),
  ('Amstel',    'Can',   '50cl',   24, 'regular', 'mainstream'),
  ('Amstel',    'Glass', '33cl',   24, 'regular', 'mainstream'),
  ('Tiger',     'Can',   '33cl',   24, 'regular', 'mainstream'),
  ('Tiger',     'Glass', '33cl',   24, 'regular', 'mainstream'),
  ('Carlsberg', 'Can',   '33cl',   24, 'regular', 'mainstream'),
  ('Carlsberg', 'Can',   '50cl',   24, 'regular', 'mainstream'),
  ('Carlsberg', 'Glass', '33cl',   24, 'regular', 'mainstream'),
  ('Budweiser', 'Can',   '35.5cl', 24, 'regular', 'mainstream'),
  ('Budweiser', 'Can',   '47.3cl', 24, 'regular', 'mainstream'),
  ('Budweiser', 'Glass', '33cl',   24, 'regular', 'mainstream')
ON CONFLICT DO NOTHING;

-- ── STRONG ────────────────────────────────────────────────────────────────────
INSERT INTO beer_pricing_analysis.beer_sku_reference (brand, pack_type, pack_size, pack, sub_type, category) VALUES
  ('Kingfisher', 'Can',   '50cl', 24, 'blue',      'strong'),
  ('Kingfisher', 'Can',   '50cl', 24, 'premium',   'strong'),
  ('Kingfisher', 'Can',   '50cl', 24, 'strong',    'strong'),
  ('Kingfisher', 'Can',   '50cl', 24, 'ultra max', 'strong'),
  ('Kingfisher', 'Glass', '33cl', 24, 'blue',      'strong'),
  ('Kingfisher', 'Glass', '33cl', 24, 'premium',   'strong'),
  ('Kingfisher', 'Glass', '33cl', 24, 'regular',   'strong'),
  ('Kingfisher', 'Glass', '33cl', 24, 'ultra',     'strong'),
  ('Kingfisher', 'Glass', '65cl', 24, 'strong',    'strong'),
  ('Red Horse',  'Can',   '50cl', 24, 'strong',    'strong'),
  ('Red Horse',  'Glass', '33cl', 24, 'strong',    'strong'),
  ('Red Horse',  'Glass', '64cl', 24, 'strong',    'strong'),
  ('Haywards',   'Can',   '50cl', 24, 'strong',    'strong')
ON CONFLICT DO NOTHING;
