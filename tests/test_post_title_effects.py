from hashlib import sha256
import unittest

from seo_agent.post_title_effects import TitleEffect, verify_title_effects


class PostTitleEffectsTests(unittest.TestCase):
    def setUp(self):
        self.current = "Original Service"
        self.proposed = "New Service"
        self.before = b"""<html><head><title>Original Service | Example</title></head><body>
<nav><a href="/service/">Original Service</a><a href="/service/">Original Service</a></nav>
<main><h1>Original Service</h1><h1>Unrelated heading</h1></main></body></html>"""
        self.after = self.before.replace(self.current.encode(), self.proposed.encode())
        self.effects = (TitleEffect("head > title", suffix=" | Example"), TitleEffect("nav a[href='/service/']", count=2),
                        TitleEffect("main h1:first-child"))

    def verify(self, before=None, after=None, effects=None):
        return verify_title_effects(self.before if before is None else before, self.after if after is None else after,
                                    current=self.current, proposed=self.proposed,
                                    effects=self.effects if effects is None else effects)

    def test_declared_delta_and_inverse_bind_the_exact_capture_bytes(self):
        result = self.verify()
        self.assertEqual(result, {"before_sha256": sha256(self.before).hexdigest(),
                                  "after_sha256": sha256(self.after).hexdigest(), "substitutions": 4})
        inverse = verify_title_effects(self.after, self.before, current=self.proposed,
                                       proposed=self.current, effects=self.effects)
        self.assertEqual(inverse["after_sha256"], result["before_sha256"])

    def test_unlisted_title_occurrence_cannot_be_replaced(self):
        before = self.before.replace(b"<main>", b'<main data-title="Original Service">')
        after = before.replace(self.current.encode(), self.proposed.encode())
        with self.assertRaisesRegex(ValueError, "literal title substitutions"):
            self.verify(before, after)

    def test_unrelated_html_or_destination_drift_fails(self):
        with self.assertRaisesRegex(ValueError, "literal title substitutions"):
            self.verify(after=self.after.replace(b'/service/', b'/new-slug/'))

    def test_wrong_element_or_duplicate_selector_cannot_claim_a_change(self):
        with self.assertRaisesRegex(ValueError, "number of elements"):
            self.verify(effects=(self.effects[0], TitleEffect("nav a[href='/elsewhere/']", count=2), self.effects[2]))
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.verify(effects=(self.effects[0], TitleEffect("nav a:first-child"),
                                 TitleEffect("nav a:first-child"), self.effects[2]))

    def test_rejects_rich_elements_and_wrong_title_affixes(self):
        before = self.before.replace(b"<h1>Original Service</h1>", b"<h1><span>Original Service</span></h1>")
        after = before.replace(self.current.encode(), self.proposed.encode())
        with self.assertRaisesRegex(ValueError, "placement"):
            self.verify(before, after)
        with self.assertRaisesRegex(ValueError, "text"):
            self.verify(effects=(TitleEffect("head > title"), *self.effects[1:]))

    def test_selector_cannot_switch_elements_and_hide_an_attribute_change(self):
        before = (b'<html><head><title>Example</title></head><body><main data-state="Original Service">'
                  b'<h1>Original&#32;Service</h1><h2>New Service</h2></main></body></html>')
        after = before.replace(b'data-state="Original Service"', b'data-state="New Service"')
        effect = TitleEffect('main[data-state="Original Service"] h1, main[data-state="New Service"] h2')
        with self.assertRaisesRegex(ValueError, "different elements"):
            self.verify(before, after, effects=(effect,))

    def test_entity_cannot_hide_a_substitution_in_the_title_affix(self):
        before = b'<html><head><title>Example</title></head><body><h1>A&#65;</h1></body></html>'
        after = before.replace(b'>A&#65;', b'>AA&#65;')
        with self.assertRaisesRegex(ValueError, "outside the declared text"):
            verify_title_effects(before, after, current="A", proposed="AA", effects=(TitleEffect("h1", prefix="A"),))
