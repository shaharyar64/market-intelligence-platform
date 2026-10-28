-- Add "super premium" 33cl Can variant for Birra Moretti and Peroni to the hero SKU reference list
INSERT INTO beer_pricing_analysis.beer_sku_reference (brand, pack_type, pack_size, pack, sub_type, category) VALUES
  ('Birra Moretti', 'Can', '33cl', 24, 'super premium', 'super_premium'),
  ('Peroni',         'Can', '33cl', 24, 'super premium', 'super_premium')
ON CONFLICT DO NOTHING;
