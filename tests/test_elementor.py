import copy
import json
import unittest
from dataclasses import replace

from seo_agent.elementor import map_heading, preview_heading, bind_rendered_heading
from seo_agent.wordpress import CMSFailure


class ElementorPreparationTests(unittest.TestCase):
    def setUp(self):
        self.data = [{"id": "container1", "elType": "container", "settings": {}, "elements": [
            {"id": "heading1", "elType": "widget", "widgetType": "heading", "settings": {
                "title": "Synthetic &amp; heading", "header_size": "h1"}, "elements": []},
            {"id": "paragraph1", "elType": "widget", "widgetType": "text-editor", "settings": {
                "editor": "<p>Keep adjacent synthetic content</p>"}, "elements": []}]}]
        self.raw = json.dumps(self.data, indent=2, ensure_ascii=True)
        self.mapping = map_heading(self.raw, page_id=9001, element_id="heading1")
        self.html = ('<div data-elementor-type="wp-page" data-elementor-id="9001">'
                     '<div data-id="container1">'
                     '<div data-id="heading1" data-widget_type="heading.default">'
                     '<h1>Synthetic &amp;amp; heading</h1></div></div></div>')

    def test_nested_mapping_literal_entity_preview_preserves_other_bytes(self):
        self.assertEqual(self.mapping.ancestor_ids, ("container1",))
        self.assertEqual(self.mapping.path, (0, "elements", 0, "settings", "title"))
        proposed = 'Synthetic &amp; “quoted” é heading'
        after = preview_heading(self.raw, self.mapping, proposed)
        expected = self.raw.replace(json.dumps(self.mapping.current), json.dumps(proposed, ensure_ascii=True))
        self.assertEqual(after, expected)
        mapped = map_heading(after, page_id=9001, element_id="heading1")
        self.assertEqual(mapped.current, proposed)
        # Reverse preview is semantic; serialization of the original token is preserved here.
        self.assertEqual(preview_heading(after, mapped, self.mapping.current), self.raw)
        self.assertFalse(bind_rendered_heading(self.html, self.mapping)["publishing_compatible"])

    def test_duplicate_json_keys_and_invalid_json_never_echo_input(self):
        for raw in ('[{"id":"secret-sentinel","id":"heading1"}]', '[NaN]', '[Infinity]', '[1e999]',
                    '[{"broken": "secret-sentinel"', '{"content": []}'):
            with self.assertRaises(CMSFailure) as error:
                map_heading(raw, page_id=9001, element_id="heading1")
            self.assertNotIn("secret-sentinel", str(error.exception))
            self.assertTrue(error.exception.__suppress_context__)

    def test_duplicate_or_missing_element_identity(self):
        value = copy.deepcopy(self.data)
        value[0]["elements"].append(copy.deepcopy(value[0]["elements"][0]))
        for raw, identity in ((json.dumps(value), "heading1"), (self.raw, "missing")):
            with self.assertRaises(CMSFailure):
                map_heading(raw, page_id=9001, element_id=identity)

    def test_equal_heading_text_elsewhere_is_preserved(self):
        data = copy.deepcopy(self.data)
        sibling = copy.deepcopy(data[0]["elements"][0])
        sibling["id"] = "heading2"
        data[0]["elements"].append(sibling)
        raw = json.dumps(data, indent=2)
        mapping = map_heading(raw, page_id=9001, element_id="heading1")
        preview = json.loads(preview_heading(raw, mapping, "Synthetic replacement"))
        self.assertEqual(preview[0]["elements"][0]["settings"]["title"], "Synthetic replacement")
        self.assertEqual(preview[0]["elements"][2], sibling)

    def test_dynamic_global_template_rich_linked_or_unknown_targets(self):
        for changes in ({"__dynamic__": {"title": "tag"}}, {"__globals__": {"typography": "kit"}},
                        {"template_id": 9002}, {"title": "<b>Rich</b>"},
                        {"link": {"url": "https://example.com/"}}, {"header_size": "div"}):
            value = copy.deepcopy(self.data)
            value[0]["elements"][0]["settings"].update(changes)
            with self.assertRaises(CMSFailure):
                map_heading(json.dumps(value), page_id=9001, element_id="heading1")
        for key, val in (("templateID", 9002), ("widgetType", "global")):
            value = copy.deepcopy(self.data)
            value[0]["elements"][0][key] = val
            with self.assertRaises(CMSFailure):
                map_heading(json.dumps(value), page_id=9001, element_id="heading1")

    def test_changed_adjacent_content_or_reordered_widget_blocks_preview(self):
        value = copy.deepcopy(self.data)
        value[0]["elements"][1]["settings"]["editor"] = "Changed by another editor"
        with self.assertRaises(CMSFailure):
            preview_heading(json.dumps(value), self.mapping, "New heading")
        value[0]["elements"].reverse()
        with self.assertRaises(CMSFailure):
            preview_heading(json.dumps(value), self.mapping, "New heading")
        # A page id is supplied independently, never inferred from raw JSON.
        with self.assertRaises(CMSFailure):
            bind_rendered_heading(self.html, replace(self.mapping, page_id=9002))

    def test_wrong_document_duplicate_render_rich_heading_and_link_rejected(self):
        for source in (self.html.replace('"9001"', '"9002"'), self.html + self.html,
                       self.html.replace("<h1>", "<h2>").replace("</h1>", "</h2>"),
                       self.html.replace("Synthetic &amp;amp; heading", "<em>Rich</em>"),
                       self.html.replace("<h1>", "<a><h1>").replace("</h1>", "</h1></a>"),
                       self.html.replace('"container1"', '"wrong-container"'),
                       self.html.replace('"wp-page"', '"wp-post"')):
            with self.assertRaises(CMSFailure):
                bind_rendered_heading(source, self.mapping)

    def test_whitespace_and_escaped_title_token_do_not_reserialize_siblings(self):
        raw = self.raw.replace('Synthetic &amp; heading', r'Synthetic \u0026amp; heading')
        mapping = map_heading(raw, page_id=9001, element_id="heading1")
        after = preview_heading(raw, mapping, 'New "literal" &amp; title')
        before_token = '"Synthetic ' + r'\u0026amp; heading' + '"'
        self.assertEqual(after, raw.replace(before_token, json.dumps('New "literal" &amp; title')))

    def test_empty_link_default_flags_are_supported_without_link_side_effect(self):
        data = copy.deepcopy(self.data)
        data[0]["elements"][0]["settings"]["link"] = {
            "url": "", "is_external": "", "nofollow": "", "custom_attributes": ""}
        self.assertEqual(map_heading(json.dumps(data), page_id=9001, element_id="heading1").current,
                         self.mapping.current)

    def test_malformed_json_types_reject_with_sanitized_error(self):
        for key, value in (("elType", []), ("widgetType", {}), ("settings", "secret-sentinel"),
                           ("elements", None)):
            data = copy.deepcopy(self.data)
            data[0]["elements"][0][key] = value
            with self.assertRaises(CMSFailure) as error:
                map_heading(json.dumps(data), page_id=9001, element_id="heading1")
            self.assertNotIn("secret-sentinel", str(error.exception))
        data = copy.deepcopy(self.data)
        data[0]["elements"][0]["settings"]["header_size"] = []
        with self.assertRaises(CMSFailure):
            map_heading(json.dumps(data), page_id=9001, element_id="heading1")

    def test_bounded_parser_and_forward_inverse_plain_values(self):
        for value in (True, 0, -1):
            with self.assertRaises(CMSFailure):
                map_heading(self.raw, page_id=value, element_id="heading1")
        for proposed in ("", "<b>Rich</b>", "[shortcode]", "Line\nBreak", "\x00", "\ud800", "x" * 501,
                         self.mapping.current):
            with self.assertRaises(CMSFailure):
                preview_heading(self.raw, self.mapping, proposed)
        for raw in ("[" * 80 + "0" + "]" * 80, ' ' * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(CMSFailure):
                map_heading(raw, page_id=9001, element_id="heading1")


if __name__ == "__main__":
    unittest.main()
