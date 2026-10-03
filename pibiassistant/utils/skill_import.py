# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Storing, exporting and reading the files of skill packages.

The parsing and every safety check live in ``skill_package``; this module only moves an already validated package
in and out of PA Skill / PA Skill File / private File. Nothing here executes package content.
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from pibiassistant.utils.skill_package import (
    MAX_TEXT_INLINE,
    SkillPackage,
    SkillPackageError,
    build_skill_package,
    parse_skill_package,
)

MAX_BLOB_READ = 10 * 1024 * 1024
STATUSES = ("Draft", "Published")
VISIBILITIES = ("Private", "Shared", "Public")


class SkillImportError(SkillPackageError):
    """A refusal the administrator can act on."""


def schema_ready() -> bool:
    """False on a site that has not migrated the package schema: every caller then behaves as before."""
    try:
        return bool(frappe.db.table_exists("PA Skill File") and frappe.get_meta("PA Skill").has_field("files"))
    except Exception:
        return False


def _title(name: str, frontmatter: Dict[str, Any]) -> str:
    given = frontmatter.get("title")
    return str(given)[:140] if isinstance(given, str) and given.strip() else name.replace("-", " ").strip().capitalize()


def _bump(version: str) -> str:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version or "")
    return f"{match.group(1)}.{match.group(2)}.{int(match.group(3)) + 1}" if match else "1.0.1"


def _extras(pkg: SkillPackage) -> Dict[str, Any]:
    return {k: v for k, v in pkg.frontmatter.items() if k not in ("name", "description")}


def _allowed_tools(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value or "")


def describe(pkg: SkillPackage) -> Dict[str, Any]:
    """Preview: what the package holds and what importing it would do, without writing anything."""
    ready = schema_ready()
    existing = frappe.db.get_value(
        "PA Skill", {"skill_id": pkg.name}, ["name", "is_system", "owner_user"] + (["version", "package_sha256"] if ready else []), as_dict=True
    )
    action = "create"
    if existing:
        if existing.is_system:
            action = "refused_system"
        elif ready and existing.package_sha256 == pkg.package_sha256:
            action = "unchanged"
        else:
            action = "update"
    return {
        "skill_id": pkg.name,
        "title": _title(pkg.name, pkg.frontmatter),
        "description": pkg.description,
        "version": pkg.version or (_bump(existing.get("version")) if action == "update" else "1.0.0"),
        "action": action,
        "existing_version": existing.get("version") if existing else None,
        "body_lines": pkg.body.count("\n") + 1,
        "files": [{"path": f.path, "kind": f.kind, "size": f.size, "is_text": f.is_text, "mime_type": f.mime_type} for f in pkg.files],
        "total_size": sum(f.size for f in pkg.files),
        "warnings": pkg.warnings,
        "package_sha256": pkg.package_sha256,
    }


def _store_file(skill_name: str, skill_id: str, f) -> Dict[str, Any]:
    row = {"path": f.path, "kind": f.kind, "is_text": 1 if f.is_text else 0, "size": f.size, "mime_type": f.mime_type, "sha256": f.sha256}
    if f.is_text and f.size <= MAX_TEXT_INLINE:
        row["text_content"] = f.data.decode("utf-8")
        return row
    stored = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"skill-{skill_id}-{f.sha256[:16]}.bin",
            "attached_to_doctype": "PA Skill",
            "attached_to_name": skill_name,
            "is_private": 1,
            "content": f.data,
        }
    )
    stored.save(ignore_permissions=True)
    row["file"] = stored.name
    return row


def _drop_stored_files(doc) -> None:
    for row in doc.get("files") or []:
        if row.file and frappe.db.exists("File", row.file):
            frappe.delete_doc("File", row.file, force=True, ignore_permissions=True)


def import_package(pkg: SkillPackage, status: str = "Draft", visibility: str = "Private", shared_roles: Optional[List[str]] = None) -> Dict[str, Any]:
    if not schema_ready():
        raise SkillImportError(_("The skill package schema is not installed on this site yet: run bench migrate first."))
    if status not in STATUSES or visibility not in VISIBILITIES:
        raise SkillImportError(_("Invalid status or visibility."))
    roles = [r for r in (shared_roles or []) if frappe.db.exists("Role", r)]
    if visibility == "Shared" and not roles:
        raise SkillImportError(_("A shared skill needs at least one role."))

    preview = describe(pkg)
    if preview["action"] == "refused_system":
        raise SkillImportError(_("{0} is a skill shipped with the system and cannot be replaced by an import. Rename the skill in SKILL.md.").format(pkg.name))
    existing_name = frappe.db.get_value("PA Skill", {"skill_id": pkg.name}, "name")
    if preview["action"] == "unchanged":
        return {**preview, "name": existing_name, "imported": False}

    version = preview["version"]
    values = {
        "title": preview["title"],
        "description": pkg.description,
        "content": pkg.body.strip() or pkg.description,
        "skill_type": "Workflow",
        "status": status,
        "visibility": visibility,
        "version": version,
        "license": str(pkg.frontmatter.get("license") or "")[:140],
        "compatibility": str(pkg.frontmatter.get("compatibility") or "")[:500],
        "allowed_tools": _allowed_tools(pkg.frontmatter.get("allowed-tools")),
        "skill_metadata": json.dumps(_extras(pkg), ensure_ascii=False, default=str),
        "source": "Imported .skill",
        "package_sha256": pkg.package_sha256,
    }
    if existing_name:
        doc = frappe.get_doc("PA Skill", existing_name)
        _drop_stored_files(doc)
        doc.set("files", [])
        doc.update(values)
    else:
        shared = [{"role": r} for r in roles] if visibility == "Shared" else []
        doc = frappe.get_doc({"doctype": "PA Skill", "skill_id": pkg.name, "owner_user": frappe.session.user, "shared_with_roles": shared, **values})
        doc.insert(ignore_permissions=True)
    doc.set("shared_with_roles", [{"role": r} for r in roles] if visibility == "Shared" else [])
    for f in pkg.files:
        doc.append("files", _store_file(doc.name, pkg.name, f))
    doc.save(ignore_permissions=True)
    # Frappe HTML-escapes text fields on save (`<output.md>` would become `&lt;output.md&gt;`), which would corrupt
    # a Markdown skill and break the export round trip. The package was validated and an administrator imported
    # it, so the exact text is written straight to the table.
    raw = {k: values[k] for k in ("content", "description", "license", "compatibility", "allowed_tools", "skill_metadata")}
    frappe.db.set_value("PA Skill", doc.name, raw, update_modified=False)
    frappe.db.commit()
    frappe.cache.hdel("skills", frappe.local.site)
    return {**preview, "name": doc.name, "imported": True, "version": version}


def import_zip_bytes(data: bytes, **options) -> Dict[str, Any]:
    return import_package(parse_skill_package(data), **options)


def file_rows(doc) -> List[Dict[str, Any]]:
    return [
        {"path": r.path, "kind": r.kind, "size": r.size, "is_text": bool(r.is_text), "mime_type": r.mime_type}
        for r in (doc.get("files") or [])
    ]


def read_file(doc, path: str) -> Dict[str, Any]:
    """The bytes of one file listed on the skill. ``path`` must match a row exactly (no traversal is possible)."""
    row = next((r for r in (doc.get("files") or []) if r.path == path), None)
    if not row:
        raise SkillImportError(_("The skill has no file {0}.").format(path[:120]))
    if row.size and row.size > MAX_BLOB_READ:
        raise SkillImportError(_("{0} is larger than the 10 MB read limit.").format(path[:120]))
    if row.file:
        content = frappe.get_doc("File", row.file).get_content()
        data = content if isinstance(content, bytes) else content.encode("utf-8")
    else:
        data = (row.text_content or "").encode("utf-8")
    if hashlib.sha256(data).hexdigest() != row.sha256:
        raise SkillImportError(_("The stored copy of {0} does not match its checksum.").format(path[:120]))
    return {"path": row.path, "kind": row.kind, "is_text": bool(row.is_text), "mime_type": row.mime_type or "application/octet-stream", "size": len(data), "data": data}


def export_package(doc) -> bytes:
    """A .skill zip for any skill; imported ones round-trip with their files and extra frontmatter."""
    extras: Dict[str, Any] = {}
    try:
        extras = json.loads(doc.get("skill_metadata") or "{}")
    except ValueError:
        extras = {}
    frontmatter: Dict[str, Any] = {"name": doc.skill_id, "description": doc.description, **extras}
    for key, value in (("license", doc.get("license")), ("compatibility", doc.get("compatibility")), ("allowed-tools", doc.get("allowed_tools"))):
        if value and key not in frontmatter:
            frontmatter[key] = value
    # An imported skill is exported exactly as it came; a version we assigned ourselves is not part of its package.
    if doc.get("version") and doc.get("source") != "Imported .skill" and not (isinstance(frontmatter.get("metadata"), dict) and frontmatter["metadata"].get("version")) and "version" not in frontmatter:
        frontmatter["metadata"] = {**(frontmatter.get("metadata") if isinstance(frontmatter.get("metadata"), dict) else {}), "version": str(doc.version)}
    files = [(r.path, read_file(doc, r.path)["data"]) for r in (doc.get("files") or [])]
    return build_skill_package(doc.skill_id, frontmatter, doc.content or "", files)
