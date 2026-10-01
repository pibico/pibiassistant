// pa_admin_prompts.js
// Prompt template management for PA Admin page.
// Extracted from pa_admin.js lines 2001-2192

(function() {
    const ns = frappe.pa_admin;

    // Load prompt templates view
    ns.loadPromptTemplatesView = function() {
        $('#prompt-templates-list').html(ns.skeletonCards(3));
        frappe.call({
            method: "pibiassistant.api.admin_api.get_prompt_templates_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.state.promptsData = response.message.templates;
                    ns.renderPromptTemplatesList();
                } else {
                    $('#prompt-templates-list').html(
                        '<div style="padding:20px;text-align:center;color:var(--red-500);">' + __('Failed to load prompt templates') + '</div>'
                    );
                }
            },
            error: function() {
                $('#prompt-templates-list').html(
                    '<div style="padding:20px;text-align:center;color:var(--red-500);">' + __('Error loading prompt templates') + '</div>'
                );
            }
        });
    };

    // Render prompt templates list
    ns.renderPromptTemplatesList = function() {
        const searchTerm = $('#prompt-search').val().toLowerCase();
        const statusFilter = $('#prompt-status-filter').val();

        const filtered = ns.state.promptsData.filter(t => {
            if (searchTerm && !t.title.toLowerCase().includes(searchTerm) &&
                !(t.prompt_id || '').toLowerCase().includes(searchTerm)) return false;
            if (statusFilter && t.status !== statusFilter) return false;
            return true;
        });

        if (filtered.length === 0) {
            const zeroData = !ns.state.promptsData || ns.state.promptsData.length === 0;
            if (zeroData) {
                $('#prompt-templates-list').html(`
                    <div class="pa-empty-state">
                        <i class="fa fa-file-text-o" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__("No prompt templates yet")}</div>
                        <div class="pa-empty-subtitle">${__("Create a prompt template to expose it to MCP clients.")}</div>
                        <a href="/app/prompt-template/new?status=Draft" class="btn btn-xs btn-primary">${__("Create template")}</a>
                    </div>
                `);
            } else {
                $('#prompt-templates-list').html(`
                    <div class="pa-empty-state">
                        <i class="fa fa-search" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__("No templates match the current filters")}</div>
                        <button type="button" class="btn btn-xs btn-default pa-clear-prompt-filters">${__("Clear filters")}</button>
                    </div>
                `);
                $('.pa-clear-prompt-filters').on('click', function() {
                    $('#prompt-search').val('');
                    $('#prompt-status-filter').val('');
                    ns.renderPromptTemplatesList();
                });
            }
            return;
        }

        const html = filtered.map(t => {
            const isToggling = ns.state.toggleInProgress[`prompt_${t.name}`];
            const isPublished = t.status === 'Published';
            const statusClass = (t.status || 'draft').toLowerCase();
            const lastUsed = t.last_used ? frappe.datetime.str_to_user(t.last_used) : __('Never');

            return `
            <div class="pa-item-card ${isToggling ? 'toggle-in-progress' : ''}" data-name="${t.name}">
                <div class="pa-item-header">
                    <div class="pa-item-title">
                        ${frappe.utils.escape_html(t.title)}
                        <span class="pa-status-badge ${statusClass}">${t.status}</span>
                    </div>
                    <div class="pa-item-actions">
                        <button class="pa-tool-settings-btn pa-prompt-preview-btn"
                                data-name="${t.name}"
                                aria-label="${__("Preview template")} ${frappe.utils.escape_html(t.title)}"
                                title="${__("Preview template")}">
                            <i class="fa fa-eye" aria-hidden="true"></i>
                        </button>
                        <a href="/app/prompt-template/${encodeURIComponent(t.name)}" target="_blank"
                           class="pa-tool-settings-btn"
                           aria-label="${__("Open in DocType")}: ${frappe.utils.escape_html(t.title)}"
                           title="${__("Open in DocType")}">
                            <i class="fa fa-external-link" aria-hidden="true"></i>
                        </a>
                        <label class="switch" style="margin:0;" title="${isPublished ? __('Click to unpublish') : __('Click to publish')}">
                            <input type="checkbox" class="pa-prompt-toggle"
                                   data-name="${t.name}"
                                   aria-label="${__("Publish prompt")} ${frappe.utils.escape_html(t.title)}"
                                   ${isPublished ? 'checked' : ''}
                                   ${isToggling ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <div class="pa-item-subtitle">${frappe.utils.escape_html(t.prompt_id || t.name)}</div>
                <div class="pa-item-meta">
                    ${t.category ? `<span class="pa-meta-chip"><i class="fa fa-folder-o"></i> ${frappe.utils.escape_html(t.category)}</span>` : ''}
                    <span class="pa-meta-chip"><i class="fa fa-eye"></i> ${__(t.visibility || 'Private')}</span>
                    ${t.is_system ? '<span class="pa-meta-chip system-chip">${__("System")}</span>' : ''}
                    <span class="pa-meta-chip">${__("Used {0}x", [t.use_count || 0])}</span>
                    <span class="pa-meta-chip"><i class="fa fa-clock-o"></i> ${lastUsed}</span>
                </div>
                <div class="pa-expand-panel" id="prompt-preview-${t.name}"></div>
            </div>`;
        }).join('');

        $('#prompt-templates-list').html(html);

        $('.pa-prompt-toggle').off('change').on('change', function() {
            ns.togglePromptTemplateStatus($(this).data('name'), $(this).is(':checked'));
        });

        $('.pa-prompt-preview-btn').off('click').on('click', function() {
            ns.showTemplatePreview($(this).data('name'));
        });
    };

    // Toggle prompt template status (publish/unpublish)
    ns.togglePromptTemplateStatus = function(name, publish) {
        const stateKey = `prompt_${name}`;
        if (ns.state.toggleInProgress[stateKey]) return;

        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

        const checkbox = $(`.pa-prompt-toggle[data-name="${name}"]`);
        const originalState = !publish;
        checkbox.prop('disabled', true);
        checkbox.closest('.pa-item-card').addClass('toggle-in-progress');

        frappe.call({
            method: "pibiassistant.api.admin_api.toggle_prompt_template_status",
            args: { name: name, publish: publish ? 1 : 0 },
            callback: function(response) {
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                if (response.message && response.message.success) {
                    frappe.show_alert({ message: response.message.message, indicator: publish ? 'green' : 'orange' });
                    const tmpl = ns.state.promptsData.find(t => t.name === name);
                    if (tmpl) tmpl.status = response.message.new_status;
                    ns.renderPromptTemplatesList();
                    ns.loadStats();
                } else {
                    checkbox.prop('checked', originalState);
                    checkbox.prop('disabled', false);
                    checkbox.closest('.pa-item-card').removeClass('toggle-in-progress');
                    frappe.show_alert({ message: response.message?.message || __('Unknown error'), indicator: 'red' });
                }
            },
            error: function() {
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;
                checkbox.prop('checked', originalState);
                checkbox.prop('disabled', false);
                checkbox.closest('.pa-item-card').removeClass('toggle-in-progress');
                frappe.show_alert({ message: __('Error toggling template status'), indicator: 'red' });
            }
        });
    };

    // Show template preview panel
    ns.showTemplatePreview = function(name) {
        const panel = $(`#prompt-preview-${name}`);
        const btn = $(`.pa-prompt-preview-btn[data-name="${name}"]`);

        if (panel.hasClass('open')) {
            panel.removeClass('open');
            btn.removeClass('active');
            return;
        }

        panel.addClass('open').html(
            '<div style="color:var(--text-muted);font-size:12px;"><i class="fa fa-spinner fa-spin"></i> ' + __("Loading preview...") + '</div>'
        );
        btn.addClass('active');

        frappe.call({
            method: "pibiassistant.api.admin_api.preview_prompt_template",
            args: { name: name },
            callback: function(response) {
                if (response.message && response.message.success) {
                    const d = response.message;
                    const argsHtml = d.arguments && d.arguments.length > 0
                        ? d.arguments.map(a =>
                            `<span class="pa-tool-badge" title="${frappe.utils.escape_html(a.description || '')}">${frappe.utils.escape_html(a.argument_name)}${a.is_required ? '*' : ''}</span>`
                        ).join(' ')
                        : '<em style="color:var(--text-muted);">' + __('No arguments') + '</em>';

                    const content = d.template_content || '';
                    const renderedContent = ns.renderMarkdown(content);

                    panel.html(`
                        <div style="margin-bottom:10px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
                            <span><strong style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">${__("Engine")}:</strong> ${frappe.utils.escape_html(d.rendering_engine || '')}</span>
                            <span><strong style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">${__("Arguments")}:</strong> ${argsHtml}</span>
                        </div>
                        <div class="pa-preview-content" style="font-size:13px;">${renderedContent}</div>
                    `);
                } else {
                    panel.html(`<div style="color:var(--red-500);">${response.message?.message || __('Failed to load preview')}</div>`);
                }
            },
            error: function() {
                panel.html('<div style="color:var(--red-500);">' + __('Error loading preview') + '</div>');
            }
        });
    };
})();
