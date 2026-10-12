import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from seo_agent import publishing as p, tracking as t
from tests import test_publishing as fixtures


def publication_app(root, sid, bid):
    from pathlib import Path
    from seo_agent.storage import Store
    from seo_agent.publication_ui import batch
    batch(Store(Path(root)), sid, bid)


class PublicationUITests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.PublishingTests()
        self.f.setUp()
        f = self.f
        self.rid = p.prepare(f.store, f.sid, f.bid, f.mapping, client_factory=f.factory)

    def tearDown(self):
        self.f.tearDown()

    def app(self):
        f = self.f
        return AppTest.from_function(publication_app, args=(str(f.store.root), f.sid, f.bid), default_timeout=20).run()

    def test_review_approval_apply_and_receipt_are_distinct_human_steps(self):
        f, app = self.f, self.app()
        self.assertFalse(app.exception)
        self.assertFalse(p.rows(f.store, f.sid, "cms_authorizations"))
        self.assertTrue(any("No editor, autosave, draft" in v.value for v in app.text))
        next(c for c in app.checkbox if c.label.startswith("I reviewed these exact CMS fields")).check()
        next(i for i in app.text_input if i.label.startswith("Responsible human")).set_value("Synthetic owner, today")
        next(i for i in app.text_input if i.label.startswith('Type "I approve these')).set_value(p.STATEMENT)
        next(b for b in app.button if b.label == "Approve exact CMS publication review").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(p.rows(f.store, f.sid, "cms_authorizations")), 1)
        self.assertEqual(f.client.writes, [])
        original = p.execute
        with patch.object(p, "execute", side_effect=lambda *a, **kw: original(*a, **kw, client_factory=f.factory)):
            next(b for b in app.button if b.label == "Apply these approved CMS actions").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Write: succeeded · Verification: passed" in v.value for v in app.text))
            next(b for b in app.button if b.label == "Apply these approved CMS actions").click().run()
        self.assertEqual(len(f.client.writes), 1)

    def test_approval_does_not_accept_blank_human_confirmation(self):
        app = self.app()
        next(b for b in app.button if b.label == "Approve exact CMS publication review").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(p.rows(self.f.store, self.f.sid, "cms_authorizations"))
        self.assertTrue(app.error)

    def test_changed_wording_blocks_old_cms_approval(self):
        f = self.f
        t.save_action(f.store, f.sid, f.aid, {**f.record["payload"], "proposed": "New wording"}, revision=3)
        app = self.app()
        next(c for c in app.checkbox if c.label.startswith("I reviewed these exact CMS fields")).check()
        next(i for i in app.text_input if i.label.startswith("Responsible human")).set_value("Synthetic owner")
        next(i for i in app.text_input if i.label.startswith('Type "I approve these')).set_value(p.STATEMENT)
        next(b for b in app.button if b.label == "Approve exact CMS publication review").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertFalse(p.rows(f.store, f.sid, "cms_authorizations"))
        self.assertFalse(f.client.writes)
