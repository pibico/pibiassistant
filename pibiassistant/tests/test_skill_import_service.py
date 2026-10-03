# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Importing, reading and exporting .skill packages through PA Skill (needs the migrated schema)."""

import glob
import hashlib
import os
import unittest
from unittest import mock

import frappe

from pibiassistant.tests.test_skill_package_parse import good_entries, make_zip
from pibiassistant.utils import skill_import
from pibiassistant.utils.skill_import import SkillImportError, export_package, import_zip_bytes, read_file
from pibiassistant.utils.skill_package import build_skill_package, parse_skill_package

PREFIX = "zz-"
NAME = "zz-import-test"


def _zip(name=NAME, body="# Demo\n\nSee references/guide.md.\n", extra=None):
    entries = {
        f"{name}/SKILL.md": f"---\nname: {name}\ndescription: Demo skill for tests.\nlicense: MIT\nmetadata:\n  version: '1.2.0'\n---\n\n{body}",
        f"{name}/references/guide.md": "# Guide\r\ntwo lines\r\n",
        f"{name}/scripts/run.py": "print('never run by the server')\n",
        f"{name}/assets/template.docx": b"PK\x03\x04\x00binary\x00\xfe\xff",
    }
    entries.update(extra or {})
    return make_zip(entries)


def _drop_all():
    for name in frappe.get_all("PA Skill", filters={"skill_id": ["like", f"{PREFIX}%"]}, pluck="name"):
        doc = frappe.get_doc("PA Skill", name)
        for row in doc.get("files") or []:
            if row.file and frappe.db.exists("File", row.file):
                frappe.delete_doc("File", row.file, force=True, ignore_permissions=True)
        frappe.delete_doc("PA Skill", name, force=True, ignore_permissions=True)
    frappe.db.commit()


class TestSkillImportService(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        if not skill_import.schema_ready():
            self.skipTest("the package schema is not migrated on this site")
        self.lang = frappe.local.lang
        frappe.local.lang = "en"
        _drop_all()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.lang = self.lang
        _drop_all()

    def _import(self, data=None, **kwargs):
        return import_zip_bytes(data or _zip(), **kwargs)

    def test_import_stores_the_skill_and_every_file(self):
        result = self._import()
        self.assertTrue(result["imported"], result)
        self.assertEqual(result["action"], "create")
        doc = frappe.get_doc("PA Skill", result["name"])
        self.assertEqual((doc.skill_id, doc.status, doc.visibility, doc.source, doc.skill_type), (NAME, "Draft", "Private", "Imported .skill", "Workflow"))
        self.assertEqual(doc.version, "1.2.0")
        self.assertEqual(doc.license, "MIT")
        self.assertTrue(doc.has_files)
        self.assertTrue(doc.content.startswith("# Demo"))
        rows = {r.path: r for r in doc.files}
        self.assertEqual(set(rows), {"assets/template.docx", "references/guide.md", "scripts/run.py"})
        self.assertTrue(rows["references/guide.md"].text_content.startswith("# Guide"))
        self.assertFalse(rows["assets/template.docx"].text_content)
        self.assertTrue(rows["assets/template.docx"].file)
        self.assertEqual(frappe.db.get_value("File", rows["assets/template.docx"].file, "is_private"), 1)

    def test_files_read_back_byte_for_byte(self):
        doc = frappe.get_doc("PA Skill", self._import()["name"])
        text = read_file(doc, "references/guide.md")
        self.assertEqual(text["data"], b"# Guide\r\ntwo lines\r\n")
        self.assertTrue(text["is_text"])
        binary = read_file(doc, "assets/template.docx")
        self.assertEqual(binary["data"], b"PK\x03\x04\x00binary\x00\xfe\xff")
        self.assertFalse(binary["is_text"])
        for bad in ("../../etc/passwd", "references/missing.md", "SKILL.md", "/etc/passwd"):
            with self.assertRaises(SkillImportError, msg=bad):
                read_file(doc, bad)

    def test_reimport_is_unchanged_then_updates_and_bumps_the_version(self):
        first = self._import()
        again = self._import()
        self.assertFalse(again["imported"])
        self.assertEqual(again["action"], "unchanged")
        changed = self._import(_zip(body="# Demo v2\n"))
        self.assertTrue(changed["imported"])
        self.assertEqual(changed["name"], first["name"])
        self.assertEqual(changed["action"], "update")
        doc = frappe.get_doc("PA Skill", first["name"])
        self.assertTrue(doc.content.startswith("# Demo v2"))
        self.assertEqual(frappe.db.count("PA Skill", {"skill_id": NAME}), 1)

    def test_version_without_metadata_is_bumped_on_update(self):
        plain = lambda body: make_zip({f"{NAME}/SKILL.md": f"---\nname: {NAME}\ndescription: d\n---\n{body}"})
        self.assertEqual(self._import(plain("one"))["version"], "1.0.0")
        self.assertEqual(self._import(plain("two"))["version"], "1.0.1")

    def test_old_stored_files_are_removed_on_update(self):
        first = self._import()
        old_file = frappe.get_doc("PA Skill", first["name"]).files[0].file
        extra = {f"{NAME}/assets/other.bin": b"\x00\x01\x02"}
        entries_without_docx = {k: v for k, v in {**_unzip(_zip())}.items() if "template.docx" not in k}
        self.assertTrue(old_file is None or frappe.db.exists("File", old_file) is not None)
        self._import(make_zip({**entries_without_docx, **extra}))
        doc = frappe.get_doc("PA Skill", first["name"])
        self.assertEqual({r.path for r in doc.files}, {"assets/other.bin", "references/guide.md", "scripts/run.py"})
        self.assertFalse(frappe.db.exists("File", {"attached_to_doctype": "PA Skill", "attached_to_name": doc.name, "file_name": ["like", "%template%"]}))

    def test_system_skills_are_never_replaced(self):
        system_id = frappe.db.get_value("PA Skill", {"is_system": 1}, "skill_id")
        if not system_id:
            self.skipTest("no system skill on this site")
        before = frappe.db.get_value("PA Skill", {"skill_id": system_id}, "content")
        with self.assertRaises(SkillImportError) as ctx:
            self._import(_zip(name=system_id))
        self.assertIn("shipped with the system", str(ctx.exception))
        self.assertEqual(frappe.db.get_value("PA Skill", {"skill_id": system_id}, "content"), before)

    def test_shared_visibility_needs_roles_and_publishing_works_for_admins(self):
        with self.assertRaises(SkillImportError):
            self._import(visibility="Shared")
        with self.assertRaises(SkillImportError):
            self._import(status="Nope")
        done = self._import(status="Published", visibility="Shared", shared_roles=["System Manager", "No Such Role"])
        doc = frappe.get_doc("PA Skill", done["name"])
        self.assertEqual((doc.status, doc.visibility), ("Published", "Shared"))
        self.assertEqual([r.role for r in doc.shared_with_roles], ["System Manager"])

    def test_export_round_trips(self):
        doc = frappe.get_doc("PA Skill", self._import()["name"])
        exported = export_package(doc)
        again = parse_skill_package(exported)
        original = parse_skill_package(_zip())
        self.assertEqual(again.package_sha256, original.package_sha256)
        self.assertEqual({f.path: f.sha256 for f in again.files}, {f.path: f.sha256 for f in original.files})
        self.assertEqual(again.frontmatter["metadata"], {"version": "1.2.0"})
        self.assertEqual(again.frontmatter["license"], "MIT")

    def test_export_of_a_plain_skill_has_frontmatter_and_body(self):
        doc = frappe.get_doc({"doctype": "PA Skill", "skill_id": "zz-plain", "title": "Plain", "description": "A plain skill.", "content": "# Hi", "skill_type": "Workflow"}).insert(ignore_permissions=True)
        pkg = parse_skill_package(export_package(doc))
        self.assertEqual((pkg.name, pkg.description, pkg.body.strip(), pkg.files), ("zz-plain", "A plain skill.", "# Hi", []))

    def test_bad_file_paths_in_a_skill_are_refused_by_the_controller(self):
        doc = frappe.get_doc({"doctype": "PA Skill", "skill_id": "zz-badpath", "title": "Bad", "description": "d", "content": "c", "skill_type": "Workflow"})
        doc.append("files", {"path": "../escape.txt", "kind": "other", "size": 1, "sha256": "x"})
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_a_bare_skill_md_creates_a_skill_with_no_files_and_exports_as_a_package(self):
        md = "---\nname: zz-bare-md\ndescription: Only instructions.\n---\n\n# Bare\n\nDo the thing.\n".encode("utf-8")
        result = self._import(md)
        self.assertTrue(result["imported"], result)
        doc = frappe.get_doc("PA Skill", result["name"])
        self.assertEqual((doc.skill_id, doc.has_files, len(doc.files), doc.source), ("zz-bare-md", 0, 0, "Imported .skill"))
        self.assertTrue(doc.content.startswith("# Bare"))
        self.assertFalse(self._import(md)["imported"])
        again = parse_skill_package(export_package(doc))
        self.assertEqual((again.name, again.files, again.body), ("zz-bare-md", [], "# Bare\n\nDo the thing."))

    def test_schema_absent_is_reported_not_crashed(self):
        with mock.patch.object(skill_import, "schema_ready", return_value=False):
            with self.assertRaises(SkillImportError) as ctx:
                self._import()
            self.assertIn("migrate", str(ctx.exception))
            preview = skill_import.describe(parse_skill_package(_zip()))
            self.assertEqual(preview["action"], "create")

    def test_describe_previews_without_writing(self):
        preview = skill_import.describe(parse_skill_package(_zip()))
        self.assertEqual((preview["skill_id"], preview["action"], preview["version"]), (NAME, "create", "1.2.0"))
        self.assertEqual(len(preview["files"]), 3)
        self.assertFalse(frappe.db.exists("PA Skill", {"skill_id": NAME}))


def _unzip(data):
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.filename.endswith("/")}


REAL_DIR = "/home/erpnext/.services/documents"


class TestRealPackages(unittest.TestCase):
    """The user's own .skill files, imported under a zz- name and compared with the zip entry by entry."""

    def setUp(self):
        frappe.set_user("Administrator")
        if not skill_import.schema_ready():
            self.skipTest("the package schema is not migrated on this site")
        self.paths = sorted(glob.glob(os.path.join(REAL_DIR, "*.skill")))
        if not self.paths:
            self.skipTest("no real .skill files on this machine")
        _drop_all()

    def tearDown(self):
        frappe.set_user("Administrator")
        _drop_all()

    def test_every_package_imports_exports_and_reads_back_identically(self):
        report = []
        for path in self.paths:
            with open(path, "rb") as handle:
                original = parse_skill_package(handle.read()) if False else None
            raw = open(path, "rb").read()
            try:
                pkg = parse_skill_package(raw)
            except Exception as e:  # a real package that fails validation is a finding, not a test crash
                report.append((os.path.basename(path), str(e)[:100]))
                continue
            renamed = parse_skill_package(
                build_skill_package(PREFIX + pkg.name, {**pkg.frontmatter, "name": PREFIX + pkg.name}, pkg.body, [(f.path, f.data) for f in pkg.files])
            )
            result = import_package_for_test(renamed)
            doc = frappe.get_doc("PA Skill", result["name"])
            self.assertEqual({r.path for r in doc.files}, {f.path for f in pkg.files}, pkg.name)
            for f in pkg.files:
                self.assertEqual(hashlib.sha256(read_file(doc, f.path)["data"]).hexdigest(), f.sha256, f"{pkg.name}:{f.path}")
            again = parse_skill_package(export_package(doc))
            self.assertEqual(again.package_sha256, renamed.package_sha256, pkg.name)
        self.assertEqual(report, [], report)


def import_package_for_test(pkg):
    return skill_import.import_package(pkg)
