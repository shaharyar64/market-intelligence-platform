-- The persona a real-estate assistant conversation is answered for.
--
-- Migration 017 dropped this column along with the food-style personas, which
-- were measured slices of the corpus used as filters. These are different: six
-- consumer perspectives defined in code (personas/definitions.py) that change
-- how an answer is prioritised and explained, never which data it reads. The
-- conversation only needs to remember which one was chosen. NULL is the
-- general view.
ALTER TABLE realestate_intel.assistant_conversations
    ADD COLUMN IF NOT EXISTS persona text;
