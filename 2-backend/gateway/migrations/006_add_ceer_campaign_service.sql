-- Register the CEER Campaign dashboard with the gateway's service-access
-- database. Admins can assign this service to individual users from the
-- existing admin UI after the migration is applied.

INSERT INTO public.services (name, code, description, route, icon, is_active)
VALUES (
    'CEER Campaign',
    'ceer-campaign',
    'CEER launch campaign performance across owned social channels.',
    '/ceer-campaign',
    'Megaphone',
    TRUE
)
ON CONFLICT (name) DO UPDATE
SET
    code = EXCLUDED.code,
    description = EXCLUDED.description,
    route = EXCLUDED.route,
    icon = EXCLUDED.icon,
    is_active = TRUE;
