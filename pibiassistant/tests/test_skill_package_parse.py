# pibiAssistant - AI Assistant integration for Frappe Framework
# AGPL-3.0 License

"""Parsing and building .skill packages (pure Python, no site needed)."""

import io
import unittest
import zipfile

from pibiassistant.utils.skill_package import (
    MAX_ENTRIES,
    SkillPackageError,
    build_skill_package,
    parse_skill_package,
)

SKILL_MD = "---\nname: demo-skill\ndescription: Does demo things. Use when asked about demos.\n---\n\n# Demo\n\nSee references/guide.md and run scripts/run.py with assets/template.docx.\n"


def make_zip(entries, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buffer.getvalue()


def good_entries(prefix="demo-skill/"):
    return {
        f"{prefix}SKILL.md": SKILL_MD,
        f"{prefix}references/guide.md": "# Guide\r\nline two\r\n",
        f"{prefix}scripts/run.py": "print('hi')\n",
        f"{prefix}assets/template.docx": b"PK\x03\x04\x00\x00binary\x00\xff",
    }


class TestParse(unittest.TestCase):
    def test_valid_package_with_a_root_folder(self):
        pkg = parse_skill_package(make_zip(good_entries()))
        self.assertEqual(pkg.name, "demo-skill")
        self.assertEqual(pkg.folder, "demo-skill")
        self.assertTrue(pkg.description.startswith("Does demo"))
        self.assertTrue(pkg.body.startswith("# Demo"))
        self.assertEqual([f.path for f in pkg.files], ["assets/template.docx", "references/guide.md", "scripts/run.py"])
        kinds = {f.path: f.kind for f in pkg.files}
        self.assertEqual(kinds, {"assets/template.docx": "asset", "references/guide.md": "reference", "scripts/run.py": "script"})
        self.assertEqual(len(pkg.package_sha256), 64)

    def test_flat_zip_is_accepted(self):
        pkg = parse_skill_package(make_zip(good_entries(prefix="")))
        self.assertEqual(pkg.name, "demo-skill")
        self.assertEqual(pkg.folder, "")

    def test_crlf_and_binary_bytes_survive(self):
        pkg = parse_skill_package(make_zip(good_entries()))
        files = {f.path: f for f in pkg.files}
        self.assertEqual(files["references/guide.md"].data, b"# Guide\r\nline two\r\n")
        self.assertTrue(files["references/guide.md"].is_text)
        self.assertFalse(files["assets/template.docx"].is_text)
        self.assertEqual(files["assets/template.docx"].data, b"PK\x03\x04\x00\x00binary\x00\xff")
        self.assertEqual(files["assets/template.docx"].size, 14)

    def test_junk_is_ignored_and_a_git_config_with_credentials_warns_without_echoing(self):
        entries = good_entries()
        token = "gh" + "p_" + "A" * 36
        entries["demo-skill/.git/config"] = f"[remote]\n\turl = https://user:{token}@github.com/x/y.git\n"
        entries["demo-skill/.git/HEAD"] = "ref: refs/heads/main\n"
        entries["demo-skill/scripts/__pycache__/run.cpython-313.pyc"] = b"\x00\x00"
        entries["demo-skill/.DS_Store"] = b"\x00"
        entries["demo-skill/.gitignore"] = "*.pyc\n"
        pkg = parse_skill_package(make_zip(entries))
        self.assertEqual([f.path for f in pkg.files], ["assets/template.docx", "references/guide.md", "scripts/run.py"])
        git = next(w for w in pkg.warnings if w["code"] == "git_ignored")
        self.assertIn("credentials", git["message"])
        self.assertIn("rotate", git["message"])
        self.assertNotIn(token, str(pkg.warnings))
        self.assertTrue(any(w["code"] == "junk_ignored" for w in pkg.warnings))

    def test_warnings_for_scripts_and_missing_referenced_files(self):
        entries = good_entries()
        del entries["demo-skill/assets/template.docx"]
        pkg = parse_skill_package(make_zip(entries))
        codes = {w["code"] for w in pkg.warnings}
        self.assertIn("scripts_not_run", codes)
        missing = [w["path"] for w in pkg.warnings if w["code"] == "missing_file"]
        self.assertEqual(missing, ["assets/template.docx"])

    def test_a_folder_named_in_prose_is_not_a_missing_file(self):
        entries = good_entries()
        entries["demo-skill/SKILL.md"] = SKILL_MD + "\nGenerated images go to assets/img and videos to assets/video.\n"
        pkg = parse_skill_package(make_zip(entries))
        self.assertEqual([w["path"] for w in pkg.warnings if w["code"] == "missing_file"], [])

    def test_secrets_block_the_import_and_never_show_the_value(self):
        key = "sk-" + "a1B2" * 12
        entries = good_entries()
        entries["demo-skill/references/guide.md"] = f"use key {key} here"
        with self.assertRaises(SkillPackageError) as ctx:
            parse_skill_package(make_zip(entries))
        self.assertIn("references/guide.md", str(ctx.exception))
        self.assertNotIn(key, str(ctx.exception))
        entries["demo-skill/references/guide.md"] = "-----BEGIN RSA PRIVATE KEY-----\nabc"
        with self.assertRaises(SkillPackageError):
            parse_skill_package(make_zip(entries))

    def test_unsafe_paths_are_refused(self):
        for bad in ("demo-skill/../evil.txt", "/abs/evil.txt", "demo-skill//x.md", "C:/evil.txt"):
            entries = good_entries()
            entries[bad] = "x"
            with self.assertRaises(SkillPackageError, msg=bad):
                parse_skill_package(make_zip(entries))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("demo-skill/SKILL.md", SKILL_MD)
            z.writestr("demo-skill\\evil.txt", "x")
        with self.assertRaises(SkillPackageError):
            parse_skill_package(buffer.getvalue())

    def test_symlinks_and_encryption_are_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("demo-skill/SKILL.md", SKILL_MD)
            info = zipfile.ZipInfo("demo-skill/link")
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "/etc/passwd")
        with self.assertRaises(SkillPackageError) as ctx:
            parse_skill_package(buffer.getvalue())
        self.assertIn("symbolic link", str(ctx.exception))

    def test_limits(self):
        with self.assertRaises(SkillPackageError):
            parse_skill_package(b"not a zip")
        with self.assertRaises(SkillPackageError):
            parse_skill_package(b"")
        many = {f"demo-skill/references/f{i}.md": "x" for i in range(MAX_ENTRIES + 1)}
        many["demo-skill/SKILL.md"] = SKILL_MD
        with self.assertRaises(SkillPackageError):
            parse_skill_package(make_zip(many))
        bomb = good_entries()
        bomb["demo-skill/assets/zeros.bin"] = b"\x00" * (3 * 1024 * 1024)
        with self.assertRaises(SkillPackageError) as ctx:
            parse_skill_package(make_zip(bomb))
        self.assertIn("zip bomb", str(ctx.exception))

    def test_frontmatter_rules(self):
        def md(front):
            return make_zip({"s/SKILL.md": f"---\n{front}\n---\nbody"})

        for front, text in (
            ("description: x", "name"),
            ("name: Bad_Name\ndescription: x", "lowercase"),
            ("name: " + "a" * 65 + "\ndescription: x", "1-64"),
            ("name: ok\ndescription: ''", "description"),
            ("name: ok\ndescription: " + "d" * 1025, "1024"),
            ("name: [unclosed\ndescription: x", "YAML"),
        ):
            with self.assertRaises(SkillPackageError, msg=front) as ctx:
                parse_skill_package(md(front))
            self.assertIn(text, str(ctx.exception), front)
        with self.assertRaises(SkillPackageError):
            parse_skill_package(make_zip({"s/SKILL.md": "no frontmatter at all"}))
        with self.assertRaises(SkillPackageError):
            parse_skill_package(make_zip({"s/other.md": "x"}))

    def test_extra_keys_version_and_folder_mismatch_warning(self):
        front = "name: demo-skill\ndescription: d\nlicense: MIT\nmetadata:\n  version: '2.1'\nallowed-tools: Read Bash\nmy-key: 7"
        pkg = parse_skill_package(make_zip({"other-folder/SKILL.md": f"---\n{front}\n---\nbody"}))
        self.assertEqual(pkg.version, "2.1")
        self.assertEqual(pkg.frontmatter["license"], "MIT")
        self.assertEqual(pkg.frontmatter["my-key"], 7)
        self.assertTrue(any(w["code"] == "folder_name" for w in pkg.warnings))


class TestStandaloneSkillMd(unittest.TestCase):
    def test_a_bare_skill_md_is_a_skill_without_files(self):
        pkg = parse_skill_package(SKILL_MD.encode("utf-8"))
        self.assertEqual((pkg.name, pkg.folder, pkg.files), ("demo-skill", "", []))
        self.assertTrue(pkg.body.startswith("# Demo"))
        self.assertTrue(any(w["code"] == "missing_file" for w in pkg.warnings))
        zipped = parse_skill_package(make_zip({"demo-skill/SKILL.md": SKILL_MD}))
        self.assertEqual(zipped.package_sha256, pkg.package_sha256)

    def test_bom_and_crlf_are_accepted(self):
        text = "\ufeff" + SKILL_MD.replace("\n", "\r\n")
        pkg = parse_skill_package(text.encode("utf-8"))
        self.assertEqual(pkg.name, "demo-skill")

    def test_other_files_are_refused_clearly(self):
        for data in (b"just some text", b"\x89PNG\r\n\x1a\n\x00\x00", "---\nname: x\n".encode("utf-8") + b"\xff\xfe", b"# Heading only\n"):
            with self.assertRaises(SkillPackageError, msg=data[:20]):
                parse_skill_package(data)

    def test_a_standalone_skill_md_still_gets_the_secret_scan_and_frontmatter_rules(self):
        token = "gh" + "p_" + "B" * 36
        with self.assertRaises(SkillPackageError):
            parse_skill_package(f"---\nname: ok\ndescription: d\n---\nuse {token}".encode("utf-8"))
        with self.assertRaises(SkillPackageError):
            parse_skill_package(b"---\nname: Bad_Name\ndescription: d\n---\nbody")


class TestBuild(unittest.TestCase):
    def test_round_trip_keeps_everything(self):
        original = parse_skill_package(make_zip(good_entries()))
        rebuilt = build_skill_package(
            original.name, original.frontmatter, original.body, [(f.path, f.data) for f in original.files]
        )
        again = parse_skill_package(rebuilt)
        self.assertEqual(again.package_sha256, original.package_sha256)
        self.assertEqual(again.frontmatter, original.frontmatter)
        self.assertEqual([(f.path, f.sha256) for f in again.files], [(f.path, f.sha256) for f in original.files])
        self.assertEqual(again.body.strip(), original.body.strip())

    def test_build_refuses_unsafe_paths(self):
        with self.assertRaises(SkillPackageError):
            build_skill_package("x", {"name": "x", "description": "d"}, "b", [("../evil", b"x")])
