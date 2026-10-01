# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Repair for GitHub issue #153.

The removed patch v2_4.rename_skill_to_pa_skill (shipped in v2.4.0) called
frappe.rename_doc("DocType", "Skill", "PA Skill") on sites where HRMS's own
"Skill" DocType existed. That rename:

  1. Rewrote every tabDocField/tabCustom Field/tabProperty Setter row whose
     Link options was "Skill" to "PA Skill", breaking HRMS doctypes
     (Employee Skill, Skill Assessment, Expected Skill Set, Designation Skill).

  2. Renamed the physical table tabSkill -> tabPA Skill. HRMS skill records
     got stranded inside tabPA Skill. A later bench migrate reloaded HRMS's
     Skill doctype fixture which recreated tabSkill empty, leaving the old
     HRMS rows mixed in with PA's SK-##### rows.

This patch undoes both effects on sites that already ran the broken patch.
It is a no-op on sites that never ran it.
"""

import frappe
from frappe.query_builder.utils import PseudoColumn


def execute():
    _repair_link_references()
    _recover_stranded_hrms_records()
    frappe.clear_cache()


def _repair_link_references():
    """Revert options='PA Skill' back to 'Skill' on non-PA parents.

    Scoped to non-Assistant Core DocTypes because PA does not ship any
    Link field pointing at its own PA Skill DocType, so every row we see
    with options='PA Skill' on a non-PA parent is corruption from the
    removed rename patch.
    """

    pa_doctypes = frappe.get_all("DocType", filters={"module": "pibiAssistant"}, pluck="name")

    DocField = frappe.qb.DocType("DocField")
    update_df = (
        frappe.qb.update(DocField)
        .set(DocField.options, "Skill")
        .where((DocField.options == "PA Skill") & (DocField.fieldtype == "Link"))
    )
    if pa_doctypes:
        update_df = update_df.where(DocField.parent.notin(pa_doctypes))
    update_df.run()

    CustomField = frappe.qb.DocType("Custom Field")
    update_cf = (
        frappe.qb.update(CustomField)
        .set(CustomField.options, "Skill")
        .where((CustomField.options == "PA Skill") & (CustomField.fieldtype == "Link"))
    )
    if pa_doctypes:
        update_cf = update_cf.where(CustomField.dt.notin(pa_doctypes))
    update_cf.run()

    PropertySetter = frappe.qb.DocType("Property Setter")
    update_ps = (
        frappe.qb.update(PropertySetter)
        .set(PropertySetter.value, "Skill")
        .where(
            (PropertySetter.property == "options")
            & (PropertySetter.value == "PA Skill")
            & (PropertySetter.field_name.notnull())
        )
    )
    if pa_doctypes:
        update_ps = update_ps.where(PropertySetter.doc_type.notin(pa_doctypes))
    update_ps.run()


def _recover_stranded_hrms_records():
    """Move HRMS skill rows out of tabPA Skill back into tabSkill.

    PA's autoname is format:SK-{#####}, so any tabPA Skill row whose name
    does not match ^SK-[0-9]+$ is a stranded HRMS record from step 2 of the
    corruption. Pull the HRMS-relevant columns, INSERT into tabSkill via
    frappe.db.bulk_insert, and delete the stranded rows from tabPA Skill.

    Some HRMS releases ship a Skill doctype with a separate ``skill_name``
    field (autoname = field:skill_name), others use ``name`` directly with
    no skill_name column. We probe for the column on both tables at runtime
    so the patch works against either schema.
    """

    if not frappe.db.exists("DocType", "Skill"):
        # Site has no HRMS Skill doctype at all; nothing to recover into.
        return

    PASkill = frappe.qb.DocType("PA Skill")
    not_fac_autoname = PseudoColumn("name NOT REGEXP '^SK-[0-9]+$'")

    has_skill_name = frappe.db.has_column("PA Skill", "skill_name") and frappe.db.has_column(
        "Skill", "skill_name"
    )

    select_query = frappe.qb.from_(PASkill).select(
        PASkill.name,
        PASkill.description,
        PASkill.creation,
        PASkill.modified,
        PASkill.modified_by,
        PASkill.owner,
        PASkill.docstatus,
        PASkill.idx,
    )
    if has_skill_name:
        select_query = select_query.select(PASkill.skill_name)

    stranded = select_query.where(not_fac_autoname).run(as_dict=True)

    if not stranded:
        return

    # Make sure tabSkill has the HRMS schema we're about to INSERT into.
    frappe.reload_doc("hr", "doctype", "skill")

    Skill = frappe.qb.DocType("Skill")
    existing = set(frappe.qb.from_(Skill).select(Skill.name).run(pluck="name"))

    to_insert = [row for row in stranded if row["name"] not in existing]

    insert_columns = [
        Skill.name,
        Skill.description,
        Skill.creation,
        Skill.modified,
        Skill.modified_by,
        Skill.owner,
        Skill.docstatus,
        Skill.idx,
    ]
    if has_skill_name:
        insert_columns.append(Skill.skill_name)

    for row in to_insert:
        values = [
            row["name"],
            row["description"],
            row["creation"],
            row["modified"],
            row["modified_by"],
            row["owner"],
            row["docstatus"],
            row["idx"],
        ]
        if has_skill_name:
            values.append(row.get("skill_name"))

        frappe.qb.into(Skill).columns(*insert_columns).insert(*values).run()

    frappe.qb.from_(PASkill).delete().where(not_fac_autoname).run()

    if to_insert:
        frappe.logger().info(
            "PA issue #153 repair: recovered %s HRMS Skill records from "
            "tabPA Skill, deleted %s stranded rows.",
            len(to_insert),
            len(stranded),
        )
