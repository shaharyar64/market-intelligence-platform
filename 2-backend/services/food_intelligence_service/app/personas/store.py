"""Persistence for personas.

A persona is stored as three separable things, and keeping them apart is the
point of this schema:

  the seed        - name, tagline, motivations, the definition text. Given to us,
                    or written by a user in chat. Never a measurement.
  the centroid    - where that definition actually lands in the corpus, learned
                    from the posts themselves rather than from the prose.
  the stats       - what the corpus says about the region around that centroid,
                    recomputed whenever the data changes.

Anything read back out can therefore be labelled as either "what you told us" or
"what the posts show", which is the only way a persona built from public posts
can be presented honestly.
"""
import json
import logging

from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("personas.store")


def ensure_table() -> None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS food_intel.personas (
                persona_id   text PRIMARY KEY,
                name         text NOT NULL,
                tagline      text,
                definition   text NOT NULL,
                motivations  text[] NOT NULL DEFAULT '{}',
                priorities   text[] NOT NULL DEFAULT '{}',
                behaviors    text[] NOT NULL DEFAULT '{}',
                centroid     vector(1024),
                model        text,
                radius       real,
                stats        jsonb NOT NULL DEFAULT '{}'::jsonb,
                origin       text NOT NULL DEFAULT 'seed',
                created_by   text,
                created_at   timestamptz NOT NULL DEFAULT now(),
                refreshed_at timestamptz
            )
        """)


def upsert(persona: dict) -> None:
    """Write a persona, preserving its id so a refresh updates in place."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO food_intel.personas
                (persona_id, name, tagline, definition, motivations, priorities,
                 behaviors, centroid, model, radius, stats, origin, created_by,
                 refreshed_at)
            VALUES (%(persona_id)s, %(name)s, %(tagline)s, %(definition)s,
                    %(motivations)s, %(priorities)s, %(behaviors)s,
                    %(centroid)s::vector, %(model)s, %(radius)s, %(stats)s,
                    %(origin)s, %(created_by)s, now())
            ON CONFLICT (persona_id) DO UPDATE SET
                name = EXCLUDED.name, tagline = EXCLUDED.tagline,
                definition = EXCLUDED.definition, motivations = EXCLUDED.motivations,
                priorities = EXCLUDED.priorities, behaviors = EXCLUDED.behaviors,
                centroid = EXCLUDED.centroid, model = EXCLUDED.model,
                radius = EXCLUDED.radius, stats = EXCLUDED.stats,
                refreshed_at = now()
                -- created_by and created_at are deliberately not updated: they
                -- record who first defined the persona, and a stats refresh is
                -- not a new definition.
        """, {**persona, "stats": json.dumps(persona.get("stats") or {})})


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# The centroid is 1024 floats. It is what makes a persona work and it is of no
# use to a caller, so it is never selected outside of centroid_of().
FIELDS = """persona_id, name, tagline, definition, motivations, priorities,
            behaviors, radius, stats, origin, refreshed_at"""


def list_personas() -> list[dict]:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT {FIELDS} FROM food_intel.personas
                        WHERE centroid IS NOT NULL ORDER BY name""")
        return _rows(cur)


def get(persona_id: str) -> dict | None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT {FIELDS} FROM food_intel.personas
                        WHERE persona_id = %s""", (persona_id,))
        found = _rows(cur)
    return found[0] if found else None


def resolve(text: str) -> dict | None:
    """Find a persona by id, exact name, or a distinctive word from its name.

    The model is given the ids, but a user says "the busy family one" and the
    model passes that through. Matching only on the id turned a persona the
    assistant had just listed into "no such persona".
    """
    needle = (text or "").strip().lower()
    if not needle:
        return None
    for persona in list_personas():
        if needle in (persona["persona_id"], persona["name"].lower()):
            return persona
    # "busy family" -> busy-family. Compared on the id's own words so a query
    # cannot match on a word every persona shares ("consumer").
    words = {w for w in needle.replace("-", " ").split() if len(w) > 3}
    best, best_overlap = None, 0
    for persona in list_personas():
        parts = set(persona["persona_id"].replace("-", " ").split())
        overlap = len(words & parts)
        if overlap > best_overlap:
            best, best_overlap = persona, overlap
    return best


def centroid_of(persona_id: str) -> tuple[list[float], float] | None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT centroid::text, radius FROM food_intel.personas
                       WHERE persona_id = %s AND centroid IS NOT NULL""",
                    (persona_id,))
        row = cur.fetchone()
    if not row:
        return None
    return [float(v) for v in row[0][1:-1].split(",")], float(row[1])
