function load_aida_models(frm, show_message) {
    frappe.call({
        method: 'pibiassistant.pibiassistant_chat.api.aida.get_models',
        callback: function(r) {
            if (r.message && r.message.success) {
                let providers = r.message.providers;
                frm._aida_providers = providers;

                let provider_names = Object.keys(providers).filter(p => providers[p].available);
                let provider_options = '\n' + provider_names.join('\n');
                frm.set_df_property('aida_default_provider', 'options', provider_options);

                update_model_options(frm);

                if (show_message) {
                    let total = provider_names.reduce((sum, p) => sum + (providers[p].models || []).length, 0);
                    frappe.show_alert({
                        message: __('{0} providers, {1} models loaded', [provider_names.length, total]),
                        indicator: 'green'
                    });
                }
            } else if (show_message) {
                frappe.show_alert({
                    message: __('Could not load models: {0}', [r.message?.error || 'API not configured']),
                    indicator: 'red'
                });
            }
        }
    });
}

function update_model_options(frm) {
    let providers = frm._aida_providers || {};
    let current_provider = frm.doc.aida_default_provider;
    let current_model = frm.doc.aida_default_model;

    if (current_provider && providers[current_provider]) {
        let models = providers[current_provider].models || [];
        let model_options = '\n' + models.join('\n');
        frm.set_df_property('aida_default_model', 'options', model_options);

        if (current_model && models.includes(current_model)) {
            frm.set_value('aida_default_model', current_model);
        }
    } else {
        frm.set_df_property('aida_default_model', 'options', '');
    }
    frm.refresh_field('aida_default_model');
}

frappe.ui.form.on("PA Core Settings", {
    refresh(frm) {
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
                    if (r.message) {
                        let html = '<div style="font-family: monospace; font-size: 13px;">';
                        for (let [name, info] of Object.entries(r.message)) {
                            let icon = info.ok ? '✅' : '❌';
                            let detail = info.ok ? info.detail : info.error;
                            html += `<p>${icon} <b>${name}</b>: ${detail}</p>`;
                        }
                        html += '</div>';
                        frappe.msgprint({title: __('AIDA API Test Results'), message: html, indicator: 'blue'});
                    }
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
            update_model_options(frm);
        }
    }
});
