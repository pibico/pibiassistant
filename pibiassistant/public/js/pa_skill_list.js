// PA Skill list view: import a Claude .skill package (SKILL.md plus references/, assets/ and scripts/) straight from
// the list. The import creates or updates the PA Skill, stores its files and opens it.
frappe.listview_settings['PA Skill'] = Object.assign(frappe.listview_settings['PA Skill'] || {}, {
    onload(listview) {
        if (!window.pibiassistant_can_manage_skills || !window.pibiassistant_can_manage_skills()) return;
        const button = listview.page.add_inner_button(__('Import .skill'), () => {
            window.pibiassistant_open_skill_import((result) => {
                if (result && result.imported && result.name) frappe.set_route('Form', 'PA Skill', result.name);
                else listview.refresh();
            });
        });
        if (button && button.prepend) button.prepend('<i class="ph ph-upload-simple" aria-hidden="true"></i> ');
    },
});
