// Our Desk form dialogs are right-edge slide panels (pibiCo rule: no centered modals).
// The PA Admin panel module and stylesheet load on demand through the server's versioned URLs.
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

// pibiAssistant - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

frappe.ui.form.on("PA Chat Settings", {
	refresh(frm) {
		// AIDA runs natively on its own API services: there is no registration to manage here,
		// only the status of the connection and the UI / retention settings below.
		frappe.call({
			method: "pibiassistant.pibiassistant_chat.api.aida.get_overview",
			callback: (r) => {
				const chat = r.message && r.message.services && r.message.services.Chat;
				frm.trigger(chat && chat.configured ? "render_connected" : "render_not_configured");
			},
			error: () => frm.trigger("render_not_configured"),
		});
	},

	render_connected(frm) {
		frm.dashboard.add_indicator(__("AIDA mode: connected to api.espib.co"), "green");
		frm.set_intro(__("AIDA is connected to its own API services. No registration is required."), "blue");
	},

	render_not_configured(frm) {
		frm.dashboard.add_indicator(__("API not configured"), "orange");
		frm.set_intro(
			__("AIDA is not configured. Ask your administrator to set it up in PA Core Settings."),
			"orange"
		);
	},
});
