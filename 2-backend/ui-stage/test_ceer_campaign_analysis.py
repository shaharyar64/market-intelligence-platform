import sys
import unittest
from datetime import date
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ceer_campaign_analysis import (
    EXCLUDED_SUB_THEMES, TAXONOMY_VERSION, THEME_TAXONOMY, classification_version,
    label_rows_by_text, matched_window,
    normalize_theme_labels, percent_change, text_key,
    validate_batch,
)


class CeerCampaignAnalysisTests(unittest.TestCase):
    def test_client_facing_taxonomy_covers_ceer_product_and_market_research_pillars(self):
        self.assertEqual(
            set(THEME_TAXONOMY),
            {
                "Launch & Brand Narrative",
                "Saudi Brand & Industrial Impact",
                "Exterior Design & Product Form",
                "Cabin & Passenger Experience",
                "Performance & Driving Dynamics",
                "Electric Capability & Regional Readiness",
                "Digital Technology & Safety",
                "Ownership & Commercial Access",
                "Brand & Market Perception",
            },
        )
        self.assertIn("Battery & Range", THEME_TAXONOMY["Electric Capability & Regional Readiness"])
        self.assertIn("Driver Assistance & Autonomous Capability", THEME_TAXONOMY["Digital Technology & Safety"])
        self.assertIn("Availability, Pre-order & Delivery", THEME_TAXONOMY["Ownership & Commercial Access"])
        self.assertEqual(
            EXCLUDED_SUB_THEMES,
            frozenset({"Emoji-only Reaction", "Unrelated or Spam", "No Usable Text"}),
        )

    def test_matched_window_uses_equal_complete_days(self):
        self.assertEqual(
            matched_window(date(2026, 9, 21), date(2026, 9, 29), date(2026, 9, 1)),
            (date(2026, 9, 12), date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 29)),
        )

    def test_matched_window_accepts_a_fixed_seven_day_period(self):
        self.assertEqual(
            matched_window(
                date(2026, 9, 21), date(2026, 9, 29), date(2026, 9, 1), days=7
            ),
            (date(2026, 9, 14), date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 27)),
        )

    def test_percent_change_does_not_invent_lift_from_zero(self):
        self.assertIsNone(percent_change(0, 10))
        self.assertEqual(percent_change(2, 3), 50.0)

    def test_text_key_is_stable_for_same_meaningful_whitespace(self):
        self.assertEqual(text_key('comment', '  سعرها   كم؟ '), text_key('comment', 'سعرها كم؟'))
        self.assertNotEqual(text_key('post', 'سعرها كم؟'), text_key('comment', 'سعرها كم؟'))

    def test_post_and_comment_taxonomy_revisions_use_separate_checkpoint_keys(self):
        self.assertNotEqual(classification_version('post'), classification_version('comment'))
        self.assertEqual(classification_version('comment'), TAXONOMY_VERSION)

    def test_normalize_theme_labels_excludes_low_signal_reactions_from_reporting(self):
        labels = normalize_theme_labels(pl.DataFrame({
            'theme': ['Data Quality (Internal)'] * 3 + ['Brand & Market Perception'],
            'sub_theme': [
                'Emoji-only Reaction',
                'Unrelated or Spam',
                'No Usable Text',
                'General Brand Reaction',
            ],
        }))

        self.assertEqual(
            labels.select('theme', 'sub_theme').rows(),
            [
                (None, None),
                (None, None),
                (None, None),
                ('Brand & Market Perception', 'General Brand Reaction'),
            ],
        )

    def test_validate_batch_rejects_missing_or_invalid_labels(self):
        good = {'item_id': 'a', 'sub_theme': 'Price, Value & Finance',
                'sentiment': 'neutral', 'confidence': 0.8, 'reason': 'Asks about price.'}
        self.assertEqual(validate_batch([good], {'a'})[0]['theme'], 'Ownership & Commercial Access')
        with self.assertRaises(ValueError):
            validate_batch([good], {'a', 'b'})
        with self.assertRaises(ValueError):
            validate_batch([{**good, 'sub_theme': 'Made up'}], {'a'})

    def test_label_rows_by_text_keeps_blank_text_and_deduplicates_repeats(self):
        rows = [
            {'comment_text': None, 'theme': 'Data Quality (Internal)', 'sub_theme': 'No Usable Text'},
            {'comment_text': 'كم السعر؟', 'theme': 'Ownership & Commercial Access', 'sub_theme': 'Price, Value & Finance'},
            {'comment_text': 'كم السعر؟', 'theme': 'Ownership & Commercial Access', 'sub_theme': 'Price, Value & Finance'},
        ]
        self.assertEqual(label_rows_by_text(rows, 'comment_text'), [
            {'raw_text': None, 'theme': 'Data Quality (Internal)', 'sub_theme': 'No Usable Text'},
            {'raw_text': 'كم السعر؟', 'theme': 'Ownership & Commercial Access', 'sub_theme': 'Price, Value & Finance'},
        ])

    def test_label_rows_by_text_rejects_conflicting_labels(self):
        rows = [
            {'post_text': 'EXOBOT', 'theme': 'Launch & Brand Narrative', 'sub_theme': 'World Premiere & Reveal'},
            {'post_text': 'EXOBOT', 'theme': 'Exterior Design & Product Form', 'sub_theme': 'Styling, Proportions & Aerodynamics'},
        ]
        with self.assertRaises(ValueError):
            label_rows_by_text(rows, 'post_text')


if __name__ == '__main__':
    unittest.main()
