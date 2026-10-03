// PA Skill form: import a .skill package from a new skill, and export any saved skill (with its files) as .skill.
frappe.ui.form.on('PA Skill', {
    refresh(frm) {
        if (!window.pibiassistant_can_manage_skills || !window.pibiassistant_can_manage_skills()) return;
        if (frm.is_new()) {
            frm.add_custom_button(__('Import .skill'), () => {
                window.pibiassistant_open_skill_import((result) => {
                    if (result && result.name) frappe.set_route('Form', 'PA Skill', result.name);
                });
            });
            return;
        }
        frm.add_custom_button(__('Export .skill'), () => {
            frappe.call({
                method: 'pibiassistant.api.admin_api.export_skill_package',
                args: { skill_id: frm.doc.skill_id },
                freeze: true,
                callback(r) {
                    const res = r.message || {};
                    if (!res.success) {
                        frappe.msgprint({ message: res.error || __('The package could not be exported.'), indicator: 'red' });
                        return;
                    }
                    const link = document.createElement('a');
                    link.href = res.file_url;
                    link.download = res.file_name;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                },
            });
        });
    },
});
