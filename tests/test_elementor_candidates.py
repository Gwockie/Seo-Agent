import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import discovery as d, elementor_candidates as c, publishing as p, tracking as t
from seo_agent.backup import _backup, _restore
from seo_agent.elementor import map_heading
from seo_agent.previews import save_preview
from seo_agent.storage import utc_now
from tests.test_tracking import TrackingFixture
from tests.test_review_previews import fixture


DYNAMIC = '[elementor-tag id="abc1234" name="post-title" settings="%7B%7D"]'
RAW = json.dumps([dict(id="root", elType="container", settings={}, elements=[
    dict(id="heading1", elType="widget", widgetType="heading", settings=dict(title="Our service", header_size="h1"), elements=[]),
    dict(id="heading2", elType="widget", widgetType="heading", settings={"title":"", "header_size":"h2", "__dynamic__":{"title":DYNAMIC}}, elements=[])
])], indent=2)
HTML = ('<html><body><div data-elementor-id="3" data-elementor-type="wp-page"><div data-id="root">'
        '<div data-id="heading1" data-widget_type="heading.default"><h1>Our service</h1></div>'
        '<div data-id="heading2" data-widget_type="heading.default"><h2>Dynamic post title</h2></div>'
        '</div></div></body></html>')


def discovery_app(root, sid):
    from pathlib import Path
    from seo_agent.storage import Store
    from seo_agent.discovery_ui import render
    render(Store(Path(root)), sid)


class CandidateTests(TrackingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.cid = d.configure(self.store, self.sid, dict(label="Production", provider="Synthetic", method="public",
            url=self.store.site(self.sid).url, environment="production", installation_id="synthetic"))
        bundle = fixture(self.sid, self.aid, self.value["url"])
        page = bundle["pages"][0]
        page["captured_utc"] = utc_now()
        heading = page["tree"]["children"][0]
        page["tree"]["children"] = [dict(id="r3", tag="div", children=[dict(id="r4", tag="div", children=[
            dict(id="r5", tag="div", children=[heading]), dict(id="r6", tag="div", children=[dict(id="r7", tag="h2", children=[dict(text="Dynamic post title")])])])])]
        save_preview(self.store, self.sid, self.aid, bundle)
        t.from_preview(self.store, self.sid, self.aid, 1)
        self.action = t.actions(self.store, self.sid)[0]
        self.public = dict(pages=[dict(id=3,url=self.value["url"],template="elementor_header_footer")],
            captures=[dict(page_id=3,url=self.value["url"],html=HTML)], clues=[])
        self.admin = dict(pages=[dict(id=3,url=self.value["url"],type="page",template="elementor_header_footer",raw_content="Synthetic mirror",
            raw_excerpt="",shared_ids=[8],metadata=[dict(row_id=42,key="_elementor_data",value=RAW)])], software=[],host=[],complete_inventory=[])
        self.seed()

    def seed(self):
        connection = d.connection(self.store, self.sid, self.cid)
        d._save(self.store, self.sid, connection, "public", self.public)
        d._save(self.store, self.sid, connection, "administrator_export", self.admin, certainty="administrator_asserted")

    def prepare(self, widget="heading1"):
        eid = c.prepare(self.store, self.sid, self.cid, self.action["action_id"], self.action["revision"], 3, widget)
        return next(r for r in d.records(self.store, self.sid, self.cid) if r["id"] == eid)

    def test_candidate_preserves_dynamic_sibling_and_exact_inverse_without_authority(self):
        row = self.prepare()
        data = row["payload"]["body"]["data"]
        self.assertEqual(data["level"], "candidate_prepared")
        candidate = data["candidate"]
        self.assertEqual(candidate["data"], RAW.replace('"Our service"', '"Our service in City"'))
        self.assertEqual(c.inverse(candidate["data"], candidate), RAW)
        self.assertEqual(candidate["preserved_dependencies"][0]["element_id"], "heading2")
        self.assertEqual(data["shared_ids"], [8])
        self.assertFalse(data["publishing_compatible"])
        self.assertEqual(d.status(self.store, self.sid, self.cid, row), "current")
        self.assertEqual(t.action(self.store,self.sid,self.action["action_id"],1),self.action)
        for table in ("cms_reviews", "cms_authorizations", "cms_attempts"):
            self.assertEqual(p.rows(self.store,self.sid,table),[])
        with self.assertRaises(ValueError):
            map_heading(candidate["data"],page_id=3,element_id="heading1")
        with self.assertRaises(ValueError):
            c.inverse(candidate["data"]+" ",candidate)

    def test_dynamic_selected_ancestor_link_rich_implicit_and_drift_block(self):
        original = copy.deepcopy(self.admin)
        changes = [dict(__dynamic__={"title":DYNAMIC}), dict(__globals__={"color":"global"}),
                   dict(link={"url":"https://example.com/"}),dict(title="<b>Rich</b>"),dict(header_size=None),
                   dict(title="Changed"),dict(title="A &amp; B"),dict(title="Line\nBreak")]
        for changeset in changes:
            with self.subTest(changes=list(changeset)):
                data=json.loads(RAW); data[0]["elements"][0]["settings"].update(changeset)
                self.admin=copy.deepcopy(original)
                self.admin["pages"][0]["metadata"][0]["value"]=json.dumps(data)
                self.seed()
                result=self.prepare()["payload"]["body"]["data"]
                self.assertIsNone(result["candidate"])
                self.assertTrue(result["preparation_blockers"])
        data=json.loads(RAW);data[0]["settings"]={"__dynamic__":{"title":DYNAMIC}}
        with self.assertRaisesRegex(ValueError,"ancestor"):
            c.inspect_heading(json.dumps(data),3,"heading1")
        self.assertIsNone(self.prepare("heading2")["payload"]["body"]["data"]["candidate"])

    def test_wrong_identity_render_target_and_url_block(self):
        original=copy.deepcopy(self.public)
        for html in (HTML.replace('data-elementor-id="3"','data-elementor-id="8"'), HTML+HTML,
                     HTML.replace("<h1>","<h1><em>").replace("</h1>","</em></h1>"),
                     HTML.replace('<div data-id="heading1"','<section data-id="heading1"').replace('</h1></div>','</h1></section>')):
            self.public=copy.deepcopy(original);self.public["captures"][0]["html"]=html;self.seed()
            self.assertIsNone(self.prepare()["payload"]["body"]["data"]["candidate"])
        self.public=copy.deepcopy(original);self.public["pages"][0]["url"]+="other/";self.seed()
        self.assertIsNone(self.prepare()["payload"]["body"]["data"]["candidate"])

    def test_latest_revision_site_and_evidence_freshness_binding(self):
        row=self.prepare()
        t.save_action(self.store,self.sid,self.aid,{**self.action["payload"],"proposed":"Revised wording"},revision=2)
        self.assertEqual(d.status(self.store,self.sid,self.cid,row),"invalidated")
        with self.assertRaisesRegex(ValueError,"latest"):
            self.prepare()
        with self.assertRaises(ValueError):
            c.prepare(self.store,self.other,self.cid,self.action["action_id"],1,3,"heading1")
        self.action=t.actions(self.store,self.sid)[0]
        row=self.prepare();self.seed()
        self.assertEqual(d.status(self.store,self.sid,self.cid,row),"invalidated")
        row=self.prepare()
        with patch("seo_agent.discovery.MAX_AGE",timedelta(seconds=-1)):
            self.assertEqual(d.status(self.store,self.sid,self.cid,row),"stale")
        d.disconnect(self.store,self.sid,self.cid)
        self.assertEqual(d.status(self.store,self.sid,self.cid,row),"invalidated")

    def test_missing_evidence_is_action_bound_blocked_report(self):
        with self.store.db() as db:
            db.execute("DELETE FROM discovery_evidence")
        row=self.prepare();data=row["payload"]["body"]["data"]
        self.assertEqual(data["level"],"blocked")
        self.assertEqual(data["audit_id"],self.aid)
        self.assertEqual(len(data["preparation_blockers"]),2)
        self.seed()
        self.assertEqual(d.status(self.store,self.sid,self.cid,row),"invalidated")

    def test_backup_candidate_is_inert_after_reconnection(self):
        self.prepare()
        archive=self.root/"backup.zip";_backup(self.store,archive)
        restored=_restore(archive,self.root/"restored")
        connection=d.connection(restored,self.sid,self.cid)
        d.configure(restored,self.sid,{k:connection[k] for k in d.Connection.model_fields},cid=self.cid)
        row=next(r for r in d.records(restored,self.sid,self.cid) if r["kind"]==c.KIND)
        self.assertEqual(d.status(restored,self.sid,self.cid,row),"invalidated")
        self.assertIsNone(p.destination(restored,self.sid))

    def test_ui_prepares_saved_revision_without_human_approval(self):
        app=AppTest.from_function(discovery_app,args=(str(self.store.root),self.sid),default_timeout=30).run()
        self.assertFalse(app.exception)
        next(x for x in app.selectbox if x.label=="Discovery environment").set_value(self.cid).run()
        self.assertFalse(app.exception)
        next(x for x in app.number_input if x.label=="Candidate CMS page ID").set_value(3)
        next(x for x in app.text_input if x.label=="Candidate heading widget ID").set_value("heading1")
        next(x for x in app.button if x.label=="Inspect saved action and prepare offline candidate").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("candidate_prepared" in x.value for x in app.text))
        self.assertEqual(p.rows(self.store,self.sid,"cms_authorizations"),[])

    def test_duplicate_invalid_json_and_secret_fields_remain_rejected(self):
        for raw in ('[{"id":"a","id":"b"}]','[NaN]',"["*80+"0"+"]"*80):
            with self.assertRaises(ValueError):c.inspect_heading(raw,3,"heading1")
        data=json.loads(RAW);data[0]["elements"].append(copy.deepcopy(data[0]["elements"][0]))
        with self.assertRaises(ValueError):c.inspect_heading(json.dumps(data),3,"heading1")
        with self.assertRaises(ValueError):d.safe_data({"api_key":"secret-sentinel"})
