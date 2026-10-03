# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _


@frappe.whitelist()
def get_skills_list() -> dict:
    """
    List all PA Skills for the admin dashboard.
    """
    frappe.only_for(["System Manager", "PA Admin"])
    try:
        from pibiassistant.utils.skill_import import schema_ready

        packaged = schema_ready()
        skills = frappe.get_all(
            "PA Skill",
            fields=[
                "name",
                "title",
                "skill_id",
                "status",
                "skill_type",
                "linked_tool",
                "use_count",
                "last_used",
                "is_system",
                "visibility",
                *(["has_files", "version", "source"] if packaged else []),
            ],
            order_by="title asc",
        )
        published = sum(1 for s in skills if s.get("status") == "Published")
        return {
            "success": True,
            "skills": skills,
            "total": len(skills),
            "published": published,
        }
    except Exception as e:
        frappe.log_error(title="Failed to get skills list", message=f"Failed to get skills list: {str(e)}")
        return {"success": False, "error": str(e), "skills": [], "total": 0, "published": 0}


@frappe.whitelist()
def get_skill_files(name: str) -> dict:
    """Files bundled with a skill (no contents), for the admin panel."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.skill_import import file_rows, schema_ready

    if not schema_ready() or not frappe.db.exists("PA Skill", name):
        return {"success": True, "files": [], "version": None, "source": None}
    doc = frappe.get_doc("PA Skill", name)
    return {"success": True, "files": file_rows(doc), "version": doc.get("version"), "source": doc.get("source"), "skill_id": doc.skill_id}


@frappe.whitelist(methods=["POST"])
def toggle_skill_status(name: str, publish: bool):
    """
    Toggle a PA Skill between Draft and Published.
    """
    frappe.only_for(["System Manager", "PA Admin"])
    try:
        if not frappe.db.exists("PA Skill", name):
            return {"success": False, "message": _("PA Skill '{0}' not found").format(name)}

        publish = frappe.utils.cint(publish)
        new_status = "Published" if publish else "Draft"

        doc = frappe.get_doc("PA Skill", name)
        doc.status = new_status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.cache.hdel("skills", frappe.local.site)

        return {
            "success": True,
            "message": _("PA Skill '{0}' set to {1}").format(doc.title, _(new_status)),
            "new_status": new_status,
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="Failed to toggle skill", message=f"Failed to toggle skill '{name}': {str(e)}")
        return {"success": False, "message": _("Error: {0}").format(str(e))}


def _read_uploaded_package(file_url: str) -> bytes:
    """The bytes of a private File the administrator just uploaded (must be theirs or readable by them)."""
    from pibiassistant.utils.skill_package import SkillPackageError

    if not file_url or not isinstance(file_url, str):
        raise SkillPackageError(_("Upload a .skill file first."))
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        raise SkillPackageError(_("The uploaded file was not found."))
    doc = frappe.get_doc("File", name)
    if not doc.has_permission("read"):
        raise SkillPackageError(_("You cannot read that file."))
    content = doc.get_content()
    return content if isinstance(content, bytes) else content.encode("utf-8")


@frappe.whitelist(methods=["POST"])
def preview_skill_package(file_url: str) -> dict:
    """What a .skill package holds and what importing it would do. Writes nothing."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.skill_import import describe, schema_ready
    from pibiassistant.utils.skill_package import SkillPackageError, parse_skill_package

    try:
        preview = describe(parse_skill_package(_read_uploaded_package(file_url)))
        return {"success": True, "schema_ready": schema_ready(), **preview}
    except SkillPackageError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        frappe.log_error(title="Skill package preview error", message=str(e)[:500])
        return {"success": False, "error": _("The package could not be read.")}


@frappe.whitelist(methods=["POST"])
def import_skill_package(file_url: str, status: str = "Draft", visibility: str = "Private", shared_roles=None) -> dict:
    """Import a .skill package (SKILL.md plus references/, assets/, scripts/) as a PA Skill. Admin only."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.skill_import import import_zip_bytes
    from pibiassistant.utils.skill_package import SkillPackageError

    roles = frappe.parse_json(shared_roles) if isinstance(shared_roles, str) else (shared_roles or [])
    try:
        result = import_zip_bytes(_read_uploaded_package(file_url), status=status, visibility=visibility, shared_roles=roles)
        return {"success": True, **result}
    except SkillPackageError as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="Skill package import error", message=str(e)[:500])
        return {"success": False, "error": _("The package could not be imported.")}


@frappe.whitelist(methods=["POST"])
def export_skill_package(skill_id: str) -> dict:
    """A .skill zip of one skill, saved as a private file for the administrator to download."""
    frappe.only_for(["System Manager", "PA Admin"])
    from pibiassistant.utils.skill_import import export_package
    from pibiassistant.utils.skill_package import SkillPackageError

    name = frappe.db.get_value("PA Skill", {"skill_id": skill_id}, "name")
    if not name:
        return {"success": False, "error": _("PA Skill '{0}' not found").format(skill_id)}
    try:
        data = export_package(frappe.get_doc("PA Skill", name))
        filename = f"{skill_id}.skill"
        for old in frappe.get_all("File", filters={"file_name": filename, "is_private": 1, "owner": frappe.session.user, "attached_to_doctype": ["is", "not set"]}, pluck="name"):
            frappe.delete_doc("File", old, force=True, ignore_permissions=True)
        saved = frappe.get_doc({"doctype": "File", "file_name": filename, "is_private": 1, "content": data})
        saved.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "file_url": saved.file_url, "file_name": filename, "size": len(data)}
    except SkillPackageError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="Skill package export error", message=str(e)[:500])
        return {"success": False, "error": _("The package could not be exported.")}
