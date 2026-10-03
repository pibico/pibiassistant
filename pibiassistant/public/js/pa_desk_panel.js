// Shared by the PA Skill list and form scripts: the PA Admin panel module and stylesheet load on demand through the
// server's content-hashed URLs, and the skill package importer opens in the same right-edge slide panel as PA Admin.
window.pibiassistant_panel = window.pibiassistant_panel || async function () {
    if (!document.getElementById('pa-admin-importmap')) {
        const versions = await frappe.xcall('pibiassistant.api.admin_api.get_import_map');
        const map = document.createElement('script');
        map.type = 'importmap';
        map.id = 'pa-admin-importmap';
        map.textContent = JSON.stringify({ imports: versions.imports });
        document.head.appendChild(map);
        if (!document.getElementById('pa-admin-css')) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.id = 'pa-admin-css';
            link.href = versions.css;
            await new Promise((resolve) => {
                link.onload = link.onerror = resolve;
                setTimeout(resolve, 3000);
                document.head.appendChild(link);
            });
        }
    }
    let host = document.getElementById('pa-desk-panel-host');
    if (!host) {
        host = document.createElement('div');
        host.id = 'pa-desk-panel-host';
        host.className = 'pa-admin-container';
        document.body.appendChild(host);
    }
    const mod = await import('/assets/pibiassistant/js/pa_admin/panel.js');
    return {
        open: (o) => mod.openPanel({ root: host, ...o }),
        confirm: (...a) => mod.confirm(...a),
        msgprint: (...a) => mod.msgprint(...a),
    };
};

// Opens the .skill import panel (upload, preview, import). `onDone(result)` runs after a successful import.
window.pibiassistant_open_skill_import = async function (onDone) {
    await window.pibiassistant_panel();
    const host = document.getElementById('pa-desk-panel-host');
    const mod = await import('/assets/pibiassistant/js/pa_admin/tabs/skills_import.js');
    return mod.openImportPanel({ root: host }, { onDone });
};

window.pibiassistant_can_manage_skills = function () {
    return frappe.user.has_role('System Manager') || frappe.user.has_role('PA Admin');
};
