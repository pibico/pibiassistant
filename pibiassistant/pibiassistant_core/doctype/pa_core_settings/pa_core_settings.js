function load_aida_models(frm, show_message) {
    frappe.call({
        method: 'pibiassistant.pibiassistant_chat.api.aida.get_models',
        callback: function(r) {
            if (r.message && r.message.success) {
                let providers = r.message.providers || {};
                frm._aida_providers = providers;

                let provider_names = Object.keys(providers).filter(p => providers[p].available);
                let provider_options = '\n' + provider_names.join('\n');
                frm.set_df_property('aida_default_provider', 'options', provider_options);
                frm.refresh_field('aida_default_provider');

                update_model_options(frm, false);

                if (show_message) {
                    let total = provider_names.reduce((sum, p) => sum + (providers[p].models || []).length, 0);
                    frappe.show_alert({
                        message: __('{0} providers, {1} models loaded', [provider_names.length, total]),
                        indicator: 'green'
                    });
                }
            } else if (show_message) {
                frappe.show_alert({
                    message: __('Could not load models: {0}', [(r.message && r.message.error) || __('API not configured')]),
                    indicator: 'red'
                });
            }
        },
        error: function() {
            if (show_message) {
                frappe.show_alert({message: __('Could not load models: {0}', [__('API not configured')]), indicator: 'red'});
            }
        }
    });
}

function update_model_options(frm, reset_invalid) {
    let providers = frm._aida_providers || {};
    let current_provider = frm.doc.aida_default_provider;
    let current_model = frm.doc.aida_default_model;

    if (current_provider && providers[current_provider]) {
        let models = providers[current_provider].models || [];
        // Keep a stored model selectable even if the API no longer lists it.
        let options = models.slice();
        if (current_model && !options.includes(current_model) && !reset_invalid) {
            options.push(current_model);
        }
        frm.set_df_property('aida_default_model', 'options', '\n' + options.join('\n'));
        if (reset_invalid && current_model && !models.includes(current_model)) {
            frm.set_value('aida_default_model', '');
        }
    } else {
        frm.set_df_property('aida_default_model', 'options', current_model ? '\n' + current_model : '');
    }
    frm.refresh_field('aida_default_model');
}

function show_aida_test_results(results) {
    let rows = Object.entries(results || {}).map(function([name, info]) {
        let icon = info.ok ? '✅' : '❌';
        let detail = info.ok ? info.detail : info.error;
        return `<p>${icon} <b>${frappe.utils.escape_html(name)}</b>: ${frappe.utils.escape_html(detail || '')}</p>`;
    });
    frappe.msgprint({
        title: __('AIDA API Test Results'),
        message: `<div style="font-family: monospace; font-size: 13px; overflow-wrap: anywhere;">${rows.join('')}</div>`,
        indicator: 'blue'
    });
}

frappe.ui.form.on("PA Core Settings", {
    refresh(frm) {
        // A long URL inside a version-log entry would otherwise widen the page on phones.
        frappe.dom.set_style('.new-timeline .timeline-content a { overflow-wrap: anywhere; }', 'pa-core-settings-style');

        frm.call('get_plugin_status').then(response => {
            if (response.message && response.message.success) {
                frm.set_df_property('plugin_status_html', 'options', response.message.html);
                frm.refresh_field('plugin_status_html');
            }
        });

        frm.add_custom_button(__('Refresh Plugin System'), function() {
            frappe.call({
                method: 'refresh_plugins',
                doc: frm.doc,
                callback: function(response) {
                    if (!response.exc) {
                        frm.reload_doc();
                    }
                }
            });
        }, __('Actions'));

        frm.add_custom_button(__('Test AIDA APIs'), function() {
            frappe.call({
                method: 'pibiassistant.pibiassistant_chat.api.aida.test_connections',
                freeze: true,
                freeze_message: __('Testing AIDA API connections...'),
                callback: function(r) {
                    if (r.message) show_aida_test_results(r.message);
                }
            });
        }, __('Actions'));

        frm.add_custom_button(__('Refresh Models'), function() {
            load_aida_models(frm, true);
        }, __('Actions'));

        load_aida_models(frm, false);
    },

    aida_default_provider(frm) {
        if (frm._aida_providers) {
            update_model_options(frm, true);
        }
    }
});
