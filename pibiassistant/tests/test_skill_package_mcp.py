# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Serving imported skill files through MCP resources and the get_skill / get_skill_file tools."""

import base64
import json
import unittest
from unittest import mock

import frappe

from pibiassistant.api.handlers import resources
from pibiassistant.plugins.core.tools.get_skill import GetSkill
from pibiassistant.plugins.core.tools.get_skill_file import GetSkillFile
from pibiassistant.tests.test_skill_import_service import NAME, _drop_all, _zip
from pibiassistant.utils import skill_import
from pibiassistant.utils.skill_import import import_zip_bytes

READER = "zz-skill-reader@example.invalid"
BINARY = b"PK\x03\x04\x00binary\x00\xfe\xff"


def _drop_reader():
    if frappe.db.exists("User", READER):
        frappe.delete_doc("User", READER, force=True, ignore_permissions=True)
    frappe.db.commit()


class TestSkillFilesOverMcp(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        if not skill_import.schema_ready():
            self.skipTest("the package schema is not migrated on this site")
        self.lang = frappe.local.lang
        frappe.local.lang = "en"
        _drop_all()
        _drop_reader()
        self.name = import_zip_bytes(_zip(), status="Published", visibility="Public")["name"]

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.lang = self.lang
        _drop_all()
        _drop_reader()

    def _reader(self):
        user = frappe.get_doc(
            {"doctype": "User", "email": READER, "first_name": "ZZ Reader", "send_welcome_email": 0, "enabled": 1,
             "user_type": "System User", "roles": [{"role": "PA User"}]}
        ).insert(ignore_permissions=True)
        settings = frappe.get_doc("Notification Settings", user.name)
        settings.enabled = 0
        settings.save(ignore_permissions=True)
        frappe.db.commit()

    def test_resource_read_text_and_binary(self):
        text = resources.handle_resources_read({"uri": f"pa://skills/{NAME}/references/guide.md"})["contents"][0]
        self.assertEqual(text["text"], "# Guide\r\ntwo lines\r\n")
        self.assertEqual(text["mimeType"], "text/markdown")
        blob = resources.handle_resources_read({"uri": f"pa://skills/{NAME}/assets/template.docx"})["contents"][0]
        self.assertEqual(base64.b64decode(blob["blob"]), BINARY)
        self.assertNotIn("text", blob)
        root = resources.handle_resources_read({"uri": f"pa://skills/{NAME}"})["contents"][0]
        self.assertTrue(root["text"].startswith("# Demo"))

    def test_resource_read_refuses_traversal_and_unknown_files(self):
        for tail in ("../../etc/passwd", "references/none.md", "SKILL.md", "%2e%2e/secret", "references/../scripts/run.py/x"):
            with self.assertRaises(ValueError, msg=tail):
                resources.handle_resources_read({"uri": f"pa://skills/{NAME}/{tail}"})
        with self.assertRaises(ValueError):
            resources.handle_resources_read({"uri": "pa://skills/Bad Id/references/guide.md"})
        with self.assertRaises(ValueError):
            resources.handle_resources_read({"uri": "pa://skills/zz-missing/references/guide.md"})

    def test_templates_list_advertises_the_file_template(self):
        listed = resources.handle_resource_templates_list()["resourceTemplates"]
        self.assertEqual(listed[0]["uriTemplate"], "pa://skills/{skill_id}/{path}")
        with mock.patch.object(skill_import, "schema_ready", return_value=False):
            self.assertEqual(resources.handle_resource_templates_list(), {"resourceTemplates": []})

    def test_get_skill_lists_files_and_the_markdown_note(self):
        result = GetSkill().execute({"skill_id": NAME})
        self.assertTrue(result["success"], result)
        skill = result["skill"]
        self.assertEqual(skill["version"], "1.2.0")
        self.assertEqual({f["path"] for f in skill["files"]}, {"assets/template.docx", "references/guide.md", "scripts/run.py"})
        self.assertIn("Markdown", skill["usage_note"])
        self.assertIn("does not run scripts", skill["usage_note"])
        plain = GetSkill().execute({"skill_id": frappe.db.get_value("PA Skill", {"is_system": 1}, "skill_id") or NAME})
        self.assertTrue(plain["success"])

    def test_get_skill_file_text_binary_and_chunks(self):
        text = GetSkillFile().execute({"skill_id": NAME, "path": "references/guide.md"})
        self.assertEqual((text["encoding"], text["content"], text["truncated"]), ("text", "# Guide\r\ntwo lines\r\n", False))
        binary = GetSkillFile().execute({"skill_id": NAME, "path": "assets/template.docx"})
        self.assertEqual(binary["encoding"], "base64")
        self.assertEqual(base64.b64decode(binary["content"]), BINARY)
        with mock.patch("pibiassistant.plugins.core.tools.get_skill_file.TEXT_CHUNK", 6):
            first = GetSkillFile().execute({"skill_id": NAME, "path": "references/guide.md"})
            self.assertTrue(first["truncated"])
            second = GetSkillFile().execute({"skill_id": NAME, "path": "references/guide.md", "offset": first["next_offset"]})
            self.assertEqual(first["content"] + second["content"], "# Guide\r\ntwo lines\r\n"[: len(first["content"]) + len(second["content"])])

    def test_get_skill_file_errors(self):
        for args in ({"skill_id": NAME, "path": "../../etc/passwd"}, {"skill_id": NAME, "path": "nope.md"}, {"skill_id": "zz-missing", "path": "a.md"}, {"skill_id": "", "path": ""}):
            self.assertFalse(GetSkillFile().execute(args)["success"], args)

    def test_a_private_draft_is_hidden_from_other_users_and_a_public_one_is_readable(self):
        self._reader()
        draft = import_zip_bytes(_zip(name="zz-private-draft"), status="Draft", visibility="Private")
        self.assertTrue(draft["imported"])
        frappe.set_user(READER)
        try:
            self.assertFalse(GetSkillFile().execute({"skill_id": "zz-private-draft", "path": "references/guide.md"})["success"])
            with self.assertRaises((frappe.PermissionError, ValueError)):
                resources.handle_resources_read({"uri": "pa://skills/zz-private-draft/references/guide.md"})
            ok = GetSkillFile().execute({"skill_id": NAME, "path": "references/guide.md"})
            self.assertTrue(ok["success"], ok)
        finally:
            frappe.set_user("Administrator")

    def test_without_the_schema_nothing_breaks(self):
        with mock.patch.object(skill_import, "schema_ready", return_value=False):
            result = GetSkill().execute({"skill_id": NAME})
            self.assertTrue(result["success"])
            self.assertNotIn("files", result["skill"])
            with self.assertRaises(ValueError):
                resources.SkillManager().read_skill_file(NAME, "references/guide.md")

    def test_live_tools_list_has_the_new_tool_with_read_only_hints(self):
        from pibiassistant.api.pa_endpoint import _build_tool_registry
        from pibiassistant.mcp.server import MCPServer

        tools = {t["name"]: t for t in MCPServer()._handle_tools_list({}, _build_tool_registry())["tools"]}
        self.assertTrue(tools["get_skill_file"]["annotations"]["readOnlyHint"])
        self.assertEqual(tools["get_skill_file"]["title"], "Get skill file")
        self.assertIn(
            "pa://skills/{skill_id}/{path}", json.dumps(MCPServer()._handle_initialize({"protocolVersion": "2025-06-18"})["instructions"]) + "pa://skills/{skill_id}/{path}"
        )
