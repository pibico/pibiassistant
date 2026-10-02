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
		frappe.call({
			method: "pibiassistant.pibiassistant_chat.api.aida.get_overview",
			callback: (r) => {
				const chat = r.message && r.message.services && r.message.services.Chat;
				if (chat && chat.configured) {
					frm.trigger("render_aida_mode");
				} else {
					frm.trigger("render_cloud_mode");
				}
			},
			error: () => frm.trigger("render_cloud_mode"),
		});
	},

	render_aida_mode(frm) {
		["section_break_ar", "tenant_id", "pa_cloud_url", "registration_status", "tenant_secret"].forEach(
			(f) => frm.toggle_display(f, false)
		);
		frm.dashboard.add_indicator(__("AIDA mode: connected to api.espib.co"), "green");
		frm.set_intro(__("AIDA is connected to its own API services. No registration is required."), "blue");
		// Every field of the first tab is hidden above; do not leave the user on an empty tab.
		const tabs = (frm.layout && frm.layout.tabs) || [];
		if (tabs.length > 1 && tabs[0].hide) {
			tabs[0].hide();
			tabs[1].set_active();
		}
	},

	render_cloud_mode(frm) {
		if (frm.doc.registration_status !== "Registered") {
			frm.add_custom_button(
				__("Register in PA Chat"),
				() => frm.trigger("start_registration"),
				__("Actions")
			);
		}

		// Nothing to clear on a site that was never registered.
		if (frm.doc.registration_status !== "Not Registered") {
			frm.add_custom_button(
				__("Reset Registration"),
				() => frm.trigger("reset_registration"),
				__("Actions")
			);
		}

		const indicators = {
			Registered: [__("Connected to cloud service"), "green"],
			"Pending Email Verification": [__("Awaiting Email Verification"), "orange"],
			Waitlisted: [__("Waitlisted"), "blue"],
			Error: [__("Registration Error"), "red"],
		};
		const [label, colour] = indicators[frm.doc.registration_status] || [
			__("Not Registered"),
			"orange",
		];
		frm.dashboard.add_indicator(label, colour);
	},

	start_registration(frm) {
		/**
		 * Registration happens in the PA Chat onboarding screen, not here.
		 *
		 * Registering means accepting a specific Terms and Conditions version,
		 * and AR rejects any registration whose terms_version it did not just
		 * publish. Terms can only be accepted where they are shown, so Desk
		 * hands off rather than posting a version it never displayed.
		 *
		 * `/aida` is a website route, not a Desk page — set_route() would
		 * resolve it under /app and 404.
		 */
		window.open("/aida", "_blank");
	},

	reset_registration(frm) {
		// Mirror of the resolved site_config value, refreshed on migrate. Shown
		// because re-registering against a different cloud service mints a NEW
		// tenant — the old subscription, credits and history stay behind.
		const pa_cloud_url = frm.doc.pa_cloud_url || __("(not configured)");

		const fail = (message) =>
			window.pibiassistant_panel().then((panels) =>
				panels.msgprint({ title: __("Reset Failed"), message })
			);
		const run = () => {
			frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.reset_registration",
				freeze: true,
				freeze_message: __("Clearing registration..."),
				callback: (r) => {
					if (r.message && r.message.success) {
						frappe.show_alert({ message: r.message.message, indicator: "green" }, 7);
						frm.reload_doc();
					} else {
						fail(frappe.utils.escape_html(r.message?.error || __("Unknown error occurred")));
					}
				},
				error: () => fail(__("Could not reach the reset endpoint.")),
			});
		};

		window.pibiassistant_panel().then((panels) => {
			const body = document.createElement("p");
			body.className = "pa-panel-text";
			body.innerHTML = __(
				"This clears the tenant credentials this site signs its requests with. PA Chat stops working until the site is registered again.<br><br>Re-registration goes to <b>{0}</b> and creates a <b>new tenant</b> there. Any subscription, credits and history belonging to the current tenant stay where they are and are not carried over.",
				[frappe.utils.escape_html(pa_cloud_url)]
			);
			panels.confirm(body, run, null, {
				title: __("Reset cloud registration?"),
				confirmLabel: __("Reset Registration"),
			});
		});
	},
});
