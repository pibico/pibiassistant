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

function load_aida_models(frm, show_message) {
    frappe.call({
        method: 'pibiassistant.pibiassistant_chat.api.aida.get_models',
        args: { refresh: show_message ? 1 : 0 },
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
        let icon = info.ok
            ? '<i class="ph ph-check-circle pa-ps-test-ok" aria-hidden="true"></i>'
            : '<i class="ph ph-x-circle pa-ps-test-fail" aria-hidden="true"></i>';
        let detail = info.ok ? info.detail : info.error;
        return `<p>${icon} <b>${frappe.utils.escape_html(name)}</b>: ${frappe.utils.escape_html(detail || '')}</p>`;
    });
    window.pibiassistant_panel().then(function(panels) {
        const body = document.createElement('div');
        body.className = 'pa-panel-text';
        body.innerHTML = rows.join('');
        panels.open({ title: __('AIDA API Test Results'), body: body });
    });
}

const LLM_API = 'pibiassistant.pibiassistant_chat.api.llm_admin.';
const LLM_AZURE_VERSION = '2024-10-21';

function llm_mode(frm) {
    return frm.doc.llm_backend_mode || 'AIDA only';
}

function llm_status_html(label, res) {
    const icon = res.ok
        ? '<i class="ph ph-check-circle pa-ps-test-ok" aria-hidden="true"></i>'
        : '<i class="ph ph-x-circle pa-ps-test-fail" aria-hidden="true"></i>';
    let text = res.ok ? (res.detail || __('Connected')) : (res.error || __('Not configured'));
    if (res.ok && res.latency_ms) text += ` (${res.latency_ms} ms)`;
    return `<p>${icon} <b>${frappe.utils.escape_html(label)}</b>: ${frappe.utils.escape_html(text)}</p>`;
}

function llm_show_panel(title, html) {
    return window.pibiassistant_panel().then(function(panels) {
        const body = document.createElement('div');
        body.className = 'pa-panel-text';
        body.innerHTML = html;
        return panels.open({ title: title, body: body });
    });
}

function llm_saved_row(row) {
    return row && row.name && !String(row.name).startsWith('new-') && !row.__islocal;
}

async function llm_test_rows(frm) {
    const rows = (frm.doc.llm_providers || []).filter(r => r.enabled);
    if (!rows.length) {
        frappe.msgprint(__('No provider is enabled, so direct models will not be available.'));
        return;
    }
    frappe.dom.freeze(__('Testing provider connections...'));
    const parts = [];
    try {
        for (const row of rows) {
            const label = row.label || row.provider_id;
            if (!llm_saved_row(row)) {
                parts.push(llm_status_html(label, { ok: false, error: __('Save the settings first.') }));
                continue;
            }
            try {
                const res = await frappe.xcall(LLM_API + 'test_provider', { row_name: row.name });
                parts.push(llm_status_html(res.label || label, res));
            } catch (e) {
                parts.push(llm_status_html(label, { ok: false, error: __('The connection test failed. Please try again.') }));
            }
        }
    } finally {
        frappe.dom.unfreeze();
    }
    llm_show_panel(__('Direct provider test results'), parts.join(''));
}

function add_action_buttons(frm) {
    const mode = llm_mode(frm);
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

    if (mode !== 'Direct providers') {
        frm.add_custom_button(__('Test AIDA APIs'), function() {
            frappe.call({
                method: 'pibiassistant.pibiassistant_chat.api.aida.test_connections',
                args: { refresh: 1 },
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
    }

    if (mode !== 'AIDA only') {
        frm.add_custom_button(__('Test direct providers'), function() {
            llm_test_rows(frm);
        }, __('Actions'));
    }
}

function llm_help_html() {
    const e = frappe.utils.escape_html;
    const link = (url) => `<a href="${url}" target="_blank" rel="noopener">${e(url.replace(/^https:\/\//, '').replace(/\/$/, ''))}</a>`;
    const items = [
        `${e(__('OpenAI: create a key at'))} ${link('https://platform.openai.com/api-keys')}. ${e(__('Responses-only models are not supported.'))}`,
        `${e(__('Anthropic: create a key at'))} ${link('https://console.anthropic.com/settings/keys')}.`,
        `${e(__('DeepSeek: create a key at'))} ${link('https://platform.deepseek.com/api_keys')}. ${e(__('Insufficient balance is reported as a billing error.'))}`,
        `${e(__('Qwen: keys are tied to a region.'))} International: https://dashscope-intl.aliyuncs.com/compatible-mode/v1 (${link('https://modelstudio.console.alibabacloud.com/')}). China: https://dashscope.aliyuncs.com/compatible-mode/v1 (${link('https://bailian.console.aliyun.com/')}). ${e(__('Leave Base URL empty for International.'))}`,
        `${e(__('xAI: create a key at'))} ${link('https://console.x.ai')}.`,
        `${e(__('Azure OpenAI: Microsoft Copilot has no public chat API; use Azure OpenAI.'))} ${e(__('Base URL is your resource endpoint'))} (https://&lt;resource&gt;.openai.azure.com). ${e(__('Enter the deployment name; list other deployments one per line in Other models. API version defaults to 2024-10-21.'))}`,
        `${e(__('Compatible: any server with an OpenAI-style /v1 API:'))} OpenRouter (https://openrouter.ai/api/v1), Mistral (https://api.mistral.ai/v1), Groq (https://api.groq.com/openai/v1), vLLM, Ollama, LM Studio. ${e(__('Servers on a private network need the site flag pa_allow_private_llm_urls set by the server administrator.'))}`,
    ];
    return '<div class="pa-ps-llm-help">'
        + `<p>${e(__('One API key per provider for the whole site. Keys are stored encrypted and never shown again. Only administrators can see this table.'))}</p>`
        + `<p>${e(__("AIDA only keeps today's behaviour. Direct providers uses only the table below. Both mixes AIDA models and direct models in the model picker. Voice dictation and document conversion always use the AIDA Voice and Convert APIs."))}</p>`
        + '<ul>' + items.map(i => `<li>${i}</li>`).join('') + '</ul></div>';
}

function llm_toggle_section(frm) {
    frm.toggle_display('llm_providers', llm_mode(frm) !== 'AIDA only');
}

function llm_load_catalog(frm) {
    if (frm._llm_catalog_promise) return frm._llm_catalog_promise;
    // The endpoint is GET-only, and frappe.xcall always posts.
    frm._llm_catalog_promise = new Promise(function(resolve, reject) {
        frappe.call({
            method: LLM_API + 'get_provider_catalog',
            type: 'GET',
            callback: r => resolve(r.message || {}),
            error: () => reject(new Error('catalog')),
        });
    }).then(function(res) {
        frm._llm_catalog = {};
        (res.providers || []).forEach(p => { frm._llm_catalog[p.id] = p; });
        return frm._llm_catalog;
    }).catch(function() {
        frm._llm_catalog = {};
        frm._llm_catalog_promise = null;
        return frm._llm_catalog;
    });
    return frm._llm_catalog_promise;
}

function llm_apply_provider(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    llm_load_catalog(frm).then(function(catalog) {
        const def = catalog[row.provider_id];
        if (!def) return;
        const grid = frm.fields_dict.llm_providers.grid;
        const presets = (def.presets || []).map(p => `${p.label || ''} ${p.base_url || p.url || ''}`.trim());
        let hint = def.base_url
            ? __('Leave empty to use the official endpoint') + ': ' + def.base_url
            : __('Base URL');
        if (presets.length) hint += ' | ' + presets.join(' | ');
        grid.update_docfield_property('base_url', 'description', hint);
        grid.update_docfield_property('base_url', 'placeholder', def.base_url || 'https://');
        if (row.provider_id === 'azure_openai' && !row.api_version) {
            frappe.model.set_value(cdt, cdn, 'api_version', LLM_AZURE_VERSION);
        }
        // keep a hand-typed label; replace an empty one or a label copied from another provider
        const known = Object.keys(catalog).map(k => catalog[k].label);
        if (!row.label || known.indexOf(row.label) !== -1) {
            frappe.model.set_value(cdt, cdn, 'label', def.label || '');
        }
    });
}

function llm_models_panel(frm, cdt, cdn, res) {
    const label = res.label || '';
    const models = (res.models || []).slice(0, 500);
    const wrap = document.createElement('div');
    wrap.className = 'pa-panel-text pa-ps-llm-models';

    if (!res.ok || !models.length) {
        const msg = document.createElement('p');
        msg.textContent = res.error || __('No models were returned.');
        wrap.appendChild(msg);
        return window.pibiassistant_panel().then(p => p.open({ title: __('Models') + ' ' + label, body: wrap }));
    }

    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'form-control pa-ps-llm-search';
    search.placeholder = __('Search');
    search.setAttribute('aria-label', __('Search'));
    wrap.appendChild(search);

    const list = document.createElement('div');
    list.className = 'pa-ps-llm-list';
    const items = models.map(function(m) {
        const id = typeof m === 'string' ? m : m.id;
        const text = (typeof m === 'string' ? m : (m.label || m.id)) || '';
        const row = document.createElement('label');
        row.className = 'pa-ps-llm-item';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.value = id;
        const span = document.createElement('span');
        span.textContent = text;
        row.append(box, span);
        list.appendChild(row);
        return { id, text: (text + ' ' + id).toLowerCase(), row, box };
    });
    wrap.appendChild(list);
    search.addEventListener('input', function() {
        const q = search.value.trim().toLowerCase();
        items.forEach(it => { it.row.hidden = q && !it.text.includes(q); });
    });

    const use = document.createElement('button');
    use.type = 'button';
    use.className = 'btn btn-primary btn-sm pa-ps-llm-use';
    use.textContent = __('Use selected');
    wrap.appendChild(use);

    return window.pibiassistant_panel().then(function(panels) {
        const panel = panels.open({ title: __('Models') + ' ' + label, body: wrap });
        use.addEventListener('click', function() {
            const picked = items.filter(it => it.box.checked).map(it => it.id);
            if (!picked.length) return;
            frappe.model.set_value(cdt, cdn, 'default_model', picked[0]);
            frappe.model.set_value(cdt, cdn, 'extra_models', picked.slice(1).join('\n'));
            if (panel && panel.close) panel.close();
            frappe.show_alert({ message: __('Save the settings to apply the selection.'), indicator: 'blue' });
        });
        return panel;
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

        add_action_buttons(frm);
        llm_toggle_section(frm);
        frm.set_df_property('llm_providers_help', 'options', llm_help_html());
        frm.refresh_field('llm_providers_help');

        load_aida_models(frm, false);
    },

    llm_backend_mode(frm) {
        llm_toggle_section(frm);
        frm.clear_custom_buttons();
        add_action_buttons(frm);
    },

    aida_default_provider(frm) {
        if (frm._aida_providers) {
            update_model_options(frm, true);
        }
    }
});

frappe.ui.form.on("PA LLM Provider", {
    form_render(frm, cdt, cdn) {
        llm_apply_provider(frm, cdt, cdn);
    },

    provider_id(frm, cdt, cdn) {
        llm_apply_provider(frm, cdt, cdn);
    },

    test_connection(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!llm_saved_row(row)) {
            frappe.msgprint(__('Save the settings first.'));
            return;
        }
        frappe.call({
            method: LLM_API + 'test_provider',
            args: { row_name: row.name },
            freeze: true,
            freeze_message: __('Testing provider connections...'),
            callback: function(r) {
                if (r.message) {
                    llm_show_panel(__('Direct provider test results'),
                        llm_status_html(r.message.label || row.label || row.provider_id, r.message));
                }
            }
        });
    },

    load_models(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!llm_saved_row(row)) {
            frappe.msgprint(__('Save the settings first.'));
            return;
        }
        frappe.call({
            method: LLM_API + 'load_provider_models',
            args: { row_name: row.name },
            freeze: true,
            freeze_message: __('Loading models...'),
            callback: function(r) {
                if (r.message) llm_models_panel(frm, cdt, cdn, r.message);
            }
        });
    }
});
