// pibiAssistant - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

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
    };
};

frappe.ui.form.on('Prompt Template', {
    refresh: function(frm) {
        // Add Preview button
        frm.add_custom_button(__('Preview'), function() {
            frm.trigger('show_preview');
        }, __('Actions'));

        // Add actions for saved documents
        if (!frm.is_new()) {
            // Create Version button (only for non-system templates)
            if (!frm.doc.is_system) {
                frm.add_custom_button(__('Create New Version'), function() {
                    frm.trigger('create_version');
                }, __('Actions'));
            }

            // Duplicate as Private button
            frm.add_custom_button(__('Duplicate as Private'), function() {
                frm.trigger('duplicate_private');
            }, __('Actions'));

            // Version History button
            frm.add_custom_button(__('Version History'), function() {
                frm.trigger('show_version_history');
            }, __('Actions'));
        }

        // Protect system templates
        if (frm.doc.is_system) {
            frm.disable_save();
            frm.set_intro(
                __('This is a system template and cannot be modified. Use "Duplicate as Private" to create your own version.'),
                'blue'
            );
        }

        // Show MCP prompt ID info
        if (frm.doc.prompt_id && frm.doc.status === 'Published') {
            frm.set_intro(
                __('MCP Prompt ID: <code>{0}</code> - Available via prompts/list', [frm.doc.prompt_id]),
                'green'
            );
        }

        // Auto-detect arguments when template content changes
        frm.trigger('check_template_arguments');
    },

    show_preview: function(frm) {
        // Collect test values for arguments
        let args = {};
        (frm.doc.arguments || []).forEach(arg => {
            args[arg.argument_name] = arg.default_value || `[${arg.argument_name}]`;
        });

        // Render preview
        frappe.call({
            method: 'pibiassistant.pibiassistant_core.doctype.prompt_template.prompt_template.preview_template',
            args: {
                template_content: frm.doc.template_content,
                rendering_engine: frm.doc.rendering_engine || 'Jinja2',
                arguments: args
            },
            callback: function(r) {
                if (!r.message) return;
                window.pibiassistant_panel().then(function(panels) {
                    const pre = document.createElement('pre');
                    pre.className = 'pa-desk-pre';
                    pre.textContent = r.message;
                    panels.open({ title: __('Template Preview'), body: pre });
                });
            }
        });
    },

    show_version_history: function(frm) {
        frappe.call({
            method: 'pibiassistant.pibiassistant_core.doctype.prompt_template.prompt_template.get_version_history',
            args: { prompt_name: frm.doc.name },
            callback: function(r) {
                window.pibiassistant_panel().then(function(panels) {
                    const esc = frappe.utils.escape_html;
                    const body = document.createElement('div');
                    const versions = r.message || [];
                    if (!versions.length) {
                        body.className = 'pa-panel-text';
                        body.textContent = __('No version history available');
                        panels.open({ title: __('Version History'), body: body });
                        return;
                    }
                    body.className = 'pa-desk-versions';
                    versions.forEach(function(v) {
                        let changes_html = (v.changes && v.changes.length)
                            ? v.changes.map(c => `<span class="pa-desk-chip">${esc(String(c[0]))}</span>`).join(' ')
                            : `<span class="pa-desk-muted">${__('No field changes recorded')}</span>`;
                        const entry = document.createElement('div');
                        entry.className = 'pa-desk-version';
                        entry.innerHTML = `
                            <div class="pa-desk-version-head">
                                <strong>${esc(frappe.datetime.str_to_user(v.modified_at))}</strong>
                                <span class="pa-desk-muted">${esc(v.modified_by)}</span>
                            </div>
                            <div class="pa-desk-version-fields">
                                <span class="pa-desk-muted">${__('Changed fields:')}</span> ${changes_html}
                            </div>
                            <button type="button" class="btn btn-xs btn-default pa-desk-restore">
                                <i class="ph ph-arrow-counter-clockwise" aria-hidden="true"></i> ${__('Restore')}
                            </button>`;
                        entry.querySelector('.pa-desk-restore').addEventListener('click', function() {
                            restore_version(panels, historyPanel, frm.doc.name, v.version_id);
                        });
                        body.appendChild(entry);
                    });
                    const historyPanel = panels.open({ title: __('Version History'), body: body });
                });
            }
        });
    },

    create_version: function(frm) {
        window.pibiassistant_panel().then(function(panels) {
            const body = document.createElement('div');
            body.innerHTML = `
                <label class="pa-desk-label" for="pa-desk-notes">${__('Version Notes')}</label>
                <textarea id="pa-desk-notes" class="pa-desk-input" rows="4"></textarea>
                <p class="pa-desk-muted">${__('Describe what changed in this version')}</p>`;
            const footer = document.createElement('div');
            footer.className = 'pa-panel-actions';
            footer.innerHTML = `
                <button type="button" class="btn btn-default pa-panel-cancel">${__('Cancel')}</button>
                <button type="button" class="btn btn-primary pa-panel-confirm">${__('Create')}</button>`;
            const panel = panels.open({ title: __('Create New Version'), body: body, footer: footer });
            footer.querySelector('.pa-panel-cancel').addEventListener('click', () => panel.close('cancel'));
            footer.querySelector('.pa-panel-confirm').addEventListener('click', function() {
                const notes = body.querySelector('textarea').value;
                panel.close('confirm');
                frappe.call({
                    method: 'create_version',
                    doc: frm.doc,
                    args: { notes: notes },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __('New version created'),
                                indicator: 'green'
                            });
                            frappe.set_route('Form', 'Prompt Template', r.message);
                        }
                    }
                });
            });
        });
    },

    duplicate_private: function(frm) {
        frappe.call({
            method: 'duplicate_as_private',
            doc: frm.doc,
            callback: function(r) {
                if (r.message) {
                    frappe.show_alert({
                        message: __('Private copy created'),
                        indicator: 'green'
                    });
                    frappe.set_route('Form', 'Prompt Template', r.message);
                }
            }
        });
    },

    template_content: function(frm) {
        // Auto-detect arguments from template
        frm.trigger('check_template_arguments');
    },

    rendering_engine: function(frm) {
        // Re-check arguments when engine changes
        frm.trigger('check_template_arguments');
    },

    check_template_arguments: function(frm) {
        if (!frm.doc.template_content) return;

        let pattern;
        if (frm.doc.rendering_engine === 'Jinja2' || !frm.doc.rendering_engine) {
            // Match {{ variable }} and {{ variable | filter }}
            pattern = /\{\{\s*(\w+)(?:\s*\|[^}]*)?\s*\}\}/g;
        } else if (frm.doc.rendering_engine === 'Format String') {
            pattern = /\{(\w+)\}/g;
        } else {
            return; // Raw mode, no placeholders
        }

        let matches = [...frm.doc.template_content.matchAll(pattern)];
        let found_args = [...new Set(matches.map(m => m[1]))];
        let existing_args = (frm.doc.arguments || []).map(a => a.argument_name);
        let new_args = found_args.filter(a => !existing_args.includes(a));
        let unused_args = existing_args.filter(a => !found_args.includes(a));

        // Show alerts for new/unused arguments
        if (new_args.length > 0) {
            frappe.show_alert({
                message: __('Found new placeholders: {0}', [new_args.join(', ')]),
                indicator: 'blue'
            }, 5);
        }

        if (unused_args.length > 0 && !frm.is_new()) {
            frappe.show_alert({
                message: __('Unused arguments: {0}', [unused_args.join(', ')]),
                indicator: 'yellow'
            }, 5);
        }
    },

    prompt_id: function(frm) {
        // Auto-convert to lowercase with underscores
        if (frm.doc.prompt_id) {
            let cleaned = frm.doc.prompt_id
                .toLowerCase()
                .replace(/\s+/g, '_')
                .replace(/[^a-z0-9_-]/g, '');

            if (cleaned !== frm.doc.prompt_id) {
                frm.set_value('prompt_id', cleaned);
                frappe.show_alert({
                    message: __('Prompt ID converted to lowercase format'),
                    indicator: 'blue'
                });
            }
        }
    },

    visibility: function(frm) {
        // Clear shared_with_roles when changing from Shared to other visibility
        if (frm.doc.visibility !== 'Shared' && frm.doc.shared_with_roles && frm.doc.shared_with_roles.length > 0) {
            window.pibiassistant_panel().then(function(panels) {
                panels.confirm(
                    __('Changing visibility will clear the shared roles. Continue?'),
                    function() {
                        frm.clear_table('shared_with_roles');
                        frm.refresh_field('shared_with_roles');
                    },
                    function() {
                        frm.set_value('visibility', 'Shared');
                    },
                    { title: __('Confirm'), confirmLabel: __('Continue') }
                );
            });
        }
    }
});

function restore_version(panels, historyPanel, prompt_name, version_id) {
    panels.confirm(
        __('Are you sure you want to restore this version? Current content will be overwritten.'),
        function() {
            frappe.call({
                method: 'pibiassistant.pibiassistant_core.doctype.prompt_template.prompt_template.restore_version',
                args: {
                    prompt_name: prompt_name,
                    version_id: version_id
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Version restored successfully'),
                            indicator: 'green'
                        });
                        historyPanel.close('restored');
                        frappe.set_route('Form', 'Prompt Template', prompt_name);
                    }
                }
            });
        },
        null,
        { title: __('Restore'), confirmLabel: __('Restore') }
    );
}

// Child table events
frappe.ui.form.on('Prompt Template Argument', {
    argument_type: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Clear allowed_values if not select/multiselect
        if (!['select', 'multiselect'].includes(row.argument_type)) {
            frappe.model.set_value(cdt, cdn, 'allowed_values', '');
        }

        // Clear length constraints if not string
        if (row.argument_type !== 'string') {
            frappe.model.set_value(cdt, cdn, 'min_length', null);
            frappe.model.set_value(cdt, cdn, 'max_length', null);
        }
    },

    argument_name: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Auto-set display label from argument name
        if (row.argument_name && !row.display_label) {
            let label = row.argument_name
                .replace(/_/g, ' ')
                .replace(/\b\w/g, l => l.toUpperCase());
            frappe.model.set_value(cdt, cdn, 'display_label', label);
        }
    }
});
