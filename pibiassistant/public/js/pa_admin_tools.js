// pa_admin_tools.js
// Tool registry, plugin management, server status, stats, and bulk actions
// for PA Admin page.
// Extracted from pa_admin.js lines 1096-1957

(function() {
    const ns = frappe.pa_admin;

    // Load server status
    ns.loadServerStatus = function() {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "PA Core Settings",
                name: "PA Core Settings"  // Required for Single DocTypes
            },
            callback: function(response) {
                if (response.message) {
                    const settings = response.message;
                    const isEnabled = settings.server_enabled;

                    // Update status
                    const statusIcon = $('#server-status-icon');
                    const statusText = $('#server-status-text');
                    const toggleBtn = $('#toggle-server');
                    const toggleText = $('#toggle-server-text');

                    const statusPill = $('#server-status-pill');
                    statusText.text('AIDA');
                    if (isEnabled) {
                        statusIcon.removeClass('inactive').addClass('active');
                        statusPill
                            .removeClass('pa-status-pill--stopped')
                            .addClass('pa-status-pill--running')
                            .html('<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Running'));
                        toggleBtn.removeClass('btn-primary').addClass('btn-danger');
                        toggleText.html('<i class="fa fa-stop" aria-hidden="true"></i> ' + __('Disable'));
                    } else {
                        statusIcon.removeClass('active').addClass('inactive');
                        statusPill
                            .removeClass('pa-status-pill--running')
                            .addClass('pa-status-pill--stopped')
                            .html('<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Stopped'));
                        toggleBtn.removeClass('btn-danger').addClass('btn-primary');
                        toggleText.html('<i class="fa fa-play" aria-hidden="true"></i> ' + __('Enable'));
                    }

                    // Update MCP Endpoint URL from settings (with fallback)
                    let endpointUrl = settings.mcp_endpoint_url;
                    if (!endpointUrl || endpointUrl === '') {
                        // Generate URL client-side if not set
                        endpointUrl = window.location.origin + '/api/method/pibiassistant.api.pa_endpoint.handle_mcp';
                    }
                    $('#pa-mcp-endpoint').text(endpointUrl);
                }
            },
            error: function(r) {
                PAOLogger.error('Failed to load server status:', r);
                $('#pa-mcp-endpoint').text(__('Error loading endpoint'));
            }
        });
    };

    // Toggle server
    ns.toggleServer = function() {
        frappe.call({
            method: "pibiassistant.api.admin_api.get_server_settings",
            callback: function(response) {
                if (!response.message) return;
                const currentState = response.message.server_enabled;
                const newState = currentState ? 0 : 1;

                const doToggle = function() {
                    frappe.call({
                        method: "pibiassistant.api.admin_api.update_server_settings",
                        args: { server_enabled: newState },
                        callback: function(result) {
                            if (result.message) {
                                frappe.show_alert({
                                    message: newState ? __('AIDA Server Enabled') : __('AIDA Server Disabled'),
                                    indicator: newState ? 'green' : 'orange'
                                });
                                setTimeout(function() { ns.loadServerStatus(); }, 300);
                            }
                        }
                    });
                };

                if (newState === 0) {
                    frappe.confirm(
                        __('Disable the AIDA server? All MCP clients will lose access until it is re-enabled.'),
                        doToggle
                    );
                } else {
                    doToggle();
                }
            }
        });
    };

    // ── PA Chat enablement ────────────────────────────────────────────
    // Reads current state from chat.api.get_chat_status and renders the
    // pill + button. The toggle endpoint returns the widget asset bundles
    // so we can hot-mount on enable without a manual page reload.

    ns.loadChatStatus = function() {
        frappe.call({
            method: "pibiassistant.pibiassistant_chat.api.get_chat_status",
            type: "GET",
            callback: function(response) {
                if (!response.message) return;
                ns._renderChatStatus(response.message.enabled);
            },
            error: function() {
                // Likely a permission denial — hide the card silently.
                $('#pa-chat-card').hide();
            }
        });
    };

    ns._renderChatStatus = function(isEnabled) {
        const pill = $('#pa-chat-status-pill');
        const btn = $('#toggle-pa-chat');
        const btnText = $('#toggle-pa-chat-text');

        if (isEnabled) {
            pill
                .removeClass('pa-status-pill--stopped')
                .addClass('pa-status-pill--running')
                .html('<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Enabled'));
            btn.removeClass('btn-primary').addClass('btn-danger');
            btnText.html('<i class="fa fa-power-off" aria-hidden="true"></i> ' + __('Disable Chat'));
        } else {
            pill
                .removeClass('pa-status-pill--running')
                .addClass('pa-status-pill--stopped')
                .html('<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Disabled'));
            btn.removeClass('btn-danger').addClass('btn-primary');
            btnText.html('<i class="fa fa-play" aria-hidden="true"></i> ' + __('Enable Chat'));
        }
    };

    ns.toggleFacChat = function() {
        // Read current state from the pill — avoids an extra round-trip.
        const isEnabled = $('#pa-chat-status-pill').hasClass('pa-status-pill--running');
        const newState = isEnabled ? 0 : 1;

        const doToggle = function() {
            $('#toggle-pa-chat').prop('disabled', true);
            frappe.call({
                method: "pibiassistant.pibiassistant_chat.api.toggle_chat",
                type: "POST",
                args: { enabled: newState },
                callback: function(result) {
                    $('#toggle-pa-chat').prop('disabled', false);
                    if (!result.message) return;
                    const data = result.message;
                    ns._renderChatStatus(data.enabled);

                    if (data.enabled) {
                        // Hot-mount the widget on this page. Other open Desk
                        // tabs will pick it up on their next navigation since
                        // can_use_pao now returns show_widget: true.
                        if (typeof window.paoWidgetRemount === 'function') {
                            window.paoWidgetRemount();
                        }
                        frappe.show_alert({
                            message: __('AIDA Chat enabled.'),
                            indicator: 'green'
                        });
                    } else {
                        // Hot-unmount the widget on this page.
                        if (typeof window.paoWidgetTeardown === 'function') {
                            window.paoWidgetTeardown();
                        }
                        frappe.show_alert({
                            message: __('AIDA Chat disabled.'),
                            indicator: 'orange'
                        });
                    }
                    // Refresh the analytics card visibility — it's gated on
                    // chat being enabled, so the card needs to appear/hide
                    // when the toggle flips.
                    if (typeof ns.loadChatAnalytics === 'function') {
                        ns.loadChatAnalytics();
                    }
                    // The AIDA Tools plugin is auto-synced with the chat
                    // toggle on the server. Refresh the tool registry so the
                    // plugin row reflects the new state without a page reload.
                    if (typeof ns.loadToolRegistry === 'function') {
                        ns.loadToolRegistry();
                    }
                },
                error: function() {
                    $('#toggle-pa-chat').prop('disabled', false);
                }
            });
        };

        if (newState === 0) {
            frappe.confirm(
                __('Disable AIDA Chat? The in-Frappe chat widget and /aida SPA will become unavailable to users.'),
                doToggle
            );
        } else {
            doToggle();
        }
    };

    // ── Chat analytics ────────────────────────────────────────────────
    // Single endpoint returns four numbers + a 30-day daily series. Card
    // is hidden when chat is disabled (server returns enabled: false).

    ns.loadChatAnalytics = function() {
        frappe.call({
            method: "pibiassistant.pibiassistant_chat.api.get_chat_analytics",
            type: "GET",
            callback: function(response) {
                const $card = $('#pa-chat-analytics-card');
                const data = response.message || {};
                if (!data.enabled) {
                    $card.hide();
                    return;
                }
                $card.show();

                $('#analytics-monthly').text(ns._fmtNumber(data.monthly_messages));
                $('#analytics-total').text(ns._fmtNumber(data.total_messages));
                $('#analytics-users').text(ns._fmtNumber(data.active_users));

                const used = data.quota_used || 0;
                const limit = data.quota_limit || 0;

                ns._renderSparkline('#analytics-spark', data.series || []);
            },
            error: function() {
                $('#pa-chat-analytics-card').hide();
            }
        });
    };

    // Inline sparkline — SVG, no external dep, scales to container width.
    // Adds a 2-unit inner margin so the stroke doesn't bleed past the card
    // edge when the first/last point sits at x=0 or x=100.
    ns._renderSparkline = function(selector, series) {
        const $host = $(selector);
        if ($host.length === 0 || !series || series.length === 0) {
            $host.empty();
            return;
        }
        const counts = series.map(d => d.count || 0);
        const max = Math.max.apply(null, counts);
        const width = 100;
        const height = 24;
        const padX = 2;
        const padY = 2;
        const innerW = width - padX * 2;
        const innerH = height - padY * 2;
        const stepX = counts.length > 1 ? (innerW / (counts.length - 1)) : 0;
        const points = counts.map((c, i) => {
            const x = (padX + i * stepX).toFixed(2);
            const y = max > 0
                ? (padY + (1 - c / max) * innerH).toFixed(2)
                : (padY + innerH);
            return `${x},${y}`;
        }).join(' ');
        const last = series[series.length - 1];
        const tip = last ? `${last.count} on ${last.day}` : '';
        $host.html(`
            <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"
                 class="pa-spark-svg" role="img" aria-label="${frappe.utils.escape_html(tip)}">
                <polyline points="${points}" />
            </svg>
        `);
    };

    ns._fmtNumber = function(n) {
        const x = Number(n || 0);
        if (x >= 1000000) return (x / 1000000).toFixed(1) + 'M';
        if (x >= 1000) return (x / 1000).toFixed(1) + 'K';
        // Round to integer for display — fractional credits look broken
        // ("32.665"); the underlying precision isn't useful at a glance.
        return String(Math.round(x));
    };

    // Populate the tab-count pills (Tools / Prompts / Skills) at the top of
    // the registry card. Replaces the old standalone stat-card grid.
    ns.loadStats = function() {
        frappe.call({
            method: "pibiassistant.api.admin_api.get_tool_stats",
            callback: function(response) {
                if (response.message) {
                    const stats = response.message;
                    $('#tab-count-tools').text(stats.total_tools || 0);
                }
            }
        });

        frappe.call({
            method: "pibiassistant.api.admin_api.get_prompt_templates_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    $('#tab-count-prompts').text(response.message.total || 0);
                }
            }
        });

        frappe.call({
            method: "pibiassistant.api.admin_api.get_skills_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    $('#tab-count-skills').text(response.message.total || 0);
                }
            }
        });
    };

    // Store tools data for filtering
    ns.toolsData = [];

    // Load tool registry based on current view mode
    ns.loadToolRegistry = function() {
        if (ns.state.viewMode === 'plugins') {
            ns.loadPluginView();
        } else {
            ns.loadToolsView();
        }
    };

    // Load plugin view (grouped by plugin)
    ns.loadPluginView = function() {
        // Skip if any toggle is in progress
        if (Object.keys(ns.state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "pibiassistant.api.admin_api.get_plugin_stats",
            callback: function(response) {
                if (response.message && response.message.plugins) {
                    const plugins = response.message.plugins;
                    if (plugins.length > 0) {
                        const pluginsHtml = plugins.map(plugin => {
                            const isToggling = ns.state.toggleInProgress[`plugin_${plugin.plugin_id}`];
                            return `
                            <div class="pa-plugin-item ${isToggling ? 'toggle-in-progress' : ''}">
                                <div class="pa-plugin-header">
                                    <div class="pa-plugin-info">
                                        <div class="pa-plugin-name">
                                            <i class="fa fa-cube"></i>
                                            ${plugin.name}
                                        </div>
                                    </div>
                                    <div>
                                        <label class="switch" style="margin: 0;">
                                            <input type="checkbox" class="pa-plugin-toggle"
                                                   data-plugin="${plugin.plugin_id}"
                                                   aria-label="${__("Enable plugin")} ${frappe.utils.escape_html(plugin.name)}"
                                                   ${plugin.enabled ? 'checked' : ''}
                                                   ${isToggling ? 'disabled' : ''}>
                                            <span class="slider round"></span>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        `}).join('');
                        $('#tool-registry').html(pluginsHtml);

                        // Add toggle handlers
                        $('.pa-plugin-toggle').off('change').on('change', function() {
                            const pluginName = $(this).data('plugin');
                            const isEnabled = $(this).is(':checked');
                            ns.togglePlugin(pluginName, isEnabled);
                        });
                    } else {
                        $('#tool-registry').html(`
                            <div class="pa-empty-state">
                                <i class="fa fa-cube" aria-hidden="true"></i>
                                <div class="pa-empty-title">${__("No plugins installed")}</div>
                                <div class="pa-empty-subtitle">${__("Install plugins to start registering tools with the MCP server.")}</div>
                            </div>
                        `);
                    }
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">' + __('Failed to load plugins') + '</div>');
            }
        });
    };

    // Load individual tools view
    ns.loadToolsView = function() {
        // Skip if any toggle is in progress
        if (Object.keys(ns.state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "pibiassistant.api.admin_api.get_tool_configurations",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.toolsData = response.message.tools;

                    // Populate plugin filter
                    const plugins = [...new Set(ns.toolsData.map(t => t.plugin_name))];
                    const pluginFilter = $('#plugin-filter');
                    pluginFilter.find('option:gt(0)').remove();
                    plugins.forEach(p => {
                        const label = p.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        pluginFilter.append(`<option value="${p}">${label}</option>`);
                    });

                    ns.renderToolsList();
                    ns.updateBulkScopeCount();
                } else {
                    $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">' + __('Failed to load tools') + '</div>');
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">' + __('Failed to load tools') + '</div>');
            }
        });
    };

    // Reset tool search / filters to defaults and re-render
    ns.clearToolFilters = function() {
        $('#tool-search').val('');
        $('#category-filter').val('');
        $('#plugin-filter').val('');
        ns.renderToolsList();
    };

    // Render filtered tools list
    ns.renderToolsList = function() {
        const searchTerm = $('#tool-search').val().toLowerCase();
        const categoryFilter = $('#category-filter').val();
        const pluginFilter = $('#plugin-filter').val();

        let filteredTools = ns.toolsData.filter(tool => {
            // Search filter
            if (searchTerm && !tool.name.toLowerCase().includes(searchTerm) &&
                !tool.description.toLowerCase().includes(searchTerm)) {
                return false;
            }
            // Category filter - treat 'privileged' and 'dangerous' as equivalent
            if (categoryFilter) {
                const toolCategory = tool.category === 'dangerous' ? 'privileged' : tool.category;
                const filterCategory = categoryFilter === 'dangerous' ? 'privileged' : categoryFilter;
                if (toolCategory !== filterCategory) {
                    return false;
                }
            }
            // Plugin filter
            if (pluginFilter && tool.plugin_name !== pluginFilter) {
                return false;
            }
            return true;
        });

        if (filteredTools.length === 0) {
            const zeroData = !ns.toolsData || ns.toolsData.length === 0;
            if (zeroData) {
                $('#tool-registry').html(`
                    <div class="pa-empty-state">
                        <i class="fa fa-wrench" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__("No tools registered")}</div>
                        <div class="pa-empty-subtitle">${__("Enable a plugin in the Plugins tab to register tools.")}</div>
                    </div>
                `);
            } else {
                $('#tool-registry').html(`
                    <div class="pa-empty-state">
                        <i class="fa fa-search" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__("No tools match the current filters")}</div>
                        <button type="button" class="btn btn-xs btn-default pa-clear-filters-btn">${__("Clear filters")}</button>
                    </div>
                `);
                $('.pa-clear-filters-btn').on('click', ns.clearToolFilters);
            }
            return;
        }

        const toolsHtml = filteredTools.map(tool => {
            const isToggling = ns.state.toggleInProgress[`tool_${tool.name}`];
            const pluginDisabled = !tool.plugin_enabled;
            const isPanelOpen = ns.state.openConfigPanels[tool.name];
            const roleTagsHtml = (tool.role_access || []).map(r =>
                `<span class="pa-role-tag" data-role="${r.role}">
                    ${r.role}
                    <button type="button" class="pa-role-remove-btn" aria-label="${__("Remove role")} ${frappe.utils.escape_html(r.role)}" data-tool="${tool.name}" data-role="${r.role}">
                        <i class="fa fa-times remove-role" data-tool="${tool.name}" data-role="${r.role}" aria-hidden="true"></i>
                    </button>
                </span>`
            ).join('');

            const q = searchTerm;
            const titleHtml = ns.highlight(tool.display_name, q);
            const descHtml = ns.highlight(tool.description || __('No description available'), q);
            return `
                <div class="pa-tool-item-detailed ${isToggling ? 'toggle-in-progress' : ''} ${pluginDisabled ? 'pa-disabled-overlay' : ''}" data-tool-name="${tool.name}">
                    <div class="pa-tool-header">
                        <div class="pa-tool-title">
                            ${titleHtml}
                            <span class="pa-category-badge ${tool.category}">${tool.category_label}</span>
                        </div>
                        <div class="pa-tool-actions">
                            <button class="pa-tool-settings-btn ${isPanelOpen ? 'active' : ''}"
                                    data-tool="${tool.name}"
                                    aria-label="${__("Configure role access")}: ${frappe.utils.escape_html(tool.display_name)}"
                                    aria-expanded="${isPanelOpen ? 'true' : 'false'}"
                                    title="${__("Configure role access")}">
                                <i class="fa fa-cog" aria-hidden="true"></i>
                            </button>
                            <label class="switch" style="margin: 0;">
                                <input type="checkbox" class="pa-tool-toggle"
                                       data-tool="${tool.name}"
                                       aria-label="${__("Enable tool")} ${frappe.utils.escape_html(tool.display_name)}"
                                       ${tool.tool_enabled ? 'checked' : ''}
                                       ${isToggling || pluginDisabled ? 'disabled' : ''}>
                                <span class="slider round"></span>
                            </label>
                        </div>
                    </div>
                    <div class="pa-tool-description-wrap">
                        <div class="pa-tool-description">${descHtml}</div>
                        <button type="button" class="pa-desc-toggle" aria-expanded="false">${__("Show more")}</button>
                    </div>
                    <div class="pa-tool-footer">
                        <span class="pa-tool-badge">${tool.plugin_display_name}</span>
                        ${pluginDisabled ? '<span class="pa-plugin-disabled-notice"><i class="fa fa-exclamation-circle"></i> ' + __('Plugin disabled') + '</span>' : ''}
                        ${tool.role_access_mode !== 'Allow All' ? '<span class="pa-tool-badge" style="background: var(--blue-100); color: var(--blue-600);"><i class="fa fa-lock"></i> ${__("Role restricted")}</span>' : ''}
                    </div>

                    <!-- Configuration Panel -->
                    <div class="pa-tool-config-panel ${isPanelOpen ? 'open' : ''}" id="config-panel-${tool.name}">
                        <div class="pa-config-row">
                            <div class="pa-config-group">
                                <label class="pa-config-label">${__("Role Access Mode")}</label>
                                <select class="pa-config-select pa-role-mode-select" data-tool="${tool.name}">
                                    <option value="Allow All" ${tool.role_access_mode === 'Allow All' ? 'selected' : ''}>${__("Allow All Users")}</option>
                                    <option value="Restrict to Listed Roles" ${tool.role_access_mode === 'Restrict to Listed Roles' ? 'selected' : ''}>${__("Restrict to Listed Roles")}</option>
                                </select>
                            </div>
                            <div class="pa-config-group">
                                <label class="pa-config-label">${__("Category")}</label>
                                <select class="pa-config-select pa-category-select" data-tool="${tool.name}">
                                    <option value="read_only" ${tool.category === 'read_only' ? 'selected' : ''}>${__("Read Only")}</option>
                                    <option value="write" ${tool.category === 'write' ? 'selected' : ''}>${__("Write")}</option>
                                    <option value="read_write" ${tool.category === 'read_write' ? 'selected' : ''}>${__("Read & Write")}</option>
                                    <option value="privileged" ${tool.category === 'privileged' || tool.category === 'dangerous' ? 'selected' : ''}>${__("Privileged")}</option>
                                </select>
                            </div>
                        </div>
                        <div class="pa-config-row pa-roles-section" data-tool="${tool.name}" style="${tool.role_access_mode !== 'Restrict to Listed Roles' ? 'display: none;' : ''}">
                            <div class="pa-config-group">
                                <label class="pa-config-label">${__("Allowed Roles")}</label>
                                <div class="pa-role-tags" id="role-tags-${tool.name}">
                                    ${roleTagsHtml}
                                    <button type="button" class="pa-add-role-btn" data-tool="${tool.name}" aria-label="${__("Add role")}: ${frappe.utils.escape_html(tool.display_name)}">
                                        <i class="fa fa-plus" aria-hidden="true"></i> Add Role
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="pa-config-actions">
                            <button class="btn btn-xs btn-default pa-config-cancel" data-tool="${tool.name}">${__("Cancel")}</button>
                            <button class="btn btn-xs btn-primary pa-config-save" data-tool="${tool.name}">${__("Save Changes")}</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        $('#tool-registry').html(toolsHtml);

        // Hide "Show more" toggle on descriptions that don't actually overflow.
        $('#tool-registry .pa-tool-description-wrap').each(function() {
            const desc = $(this).find('.pa-tool-description')[0];
            const toggle = $(this).find('.pa-desc-toggle');
            if (desc && desc.scrollHeight <= desc.clientHeight + 2) {
                toggle.hide();
            }
        });

        // Show more / Show less for long tool descriptions
        $('.pa-desc-toggle').off('click').on('click', function() {
            const $wrap = $(this).closest('.pa-tool-description-wrap');
            const expanded = $wrap.toggleClass('expanded').hasClass('expanded');
            $(this)
                .text(expanded ? __('Show less') : __('Show more'))
                .attr('aria-expanded', expanded ? 'true' : 'false');
        });

        // Add toggle handlers
        $('.pa-tool-toggle').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const isEnabled = $(this).is(':checked');
            ns.toggleTool(toolName, isEnabled);
        });

        // Add settings button handlers
        $('.pa-tool-settings-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.toggleConfigPanel(toolName);
        });

        // Add role mode change handlers
        $('.pa-role-mode-select').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const mode = $(this).val();
            const rolesSection = $(`.pa-roles-section[data-tool="${toolName}"]`);
            if (mode === 'Restrict to Listed Roles') {
                rolesSection.show();
            } else {
                rolesSection.hide();
            }
        });

        // Add role button handlers
        $('.pa-add-role-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.showAddRoleDialog(toolName);
        });

        // Remove role handlers
        $('.remove-role').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            const role = $(this).data('role');
            ns.removeRole(toolName, role);
        });

        // Cancel button handlers
        $('.pa-config-cancel').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.toggleConfigPanel(toolName, false);
            // Re-render to reset any unsaved changes
            ns.renderToolsList();
        });

        // Save button handlers
        $('.pa-config-save').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.saveToolConfig(toolName);
        });
    };

    // Toggle config panel visibility
    ns.toggleConfigPanel = function(toolName, forceState) {
        const panel = $(`#config-panel-${toolName}`);
        const btn = $(`.pa-tool-settings-btn[data-tool="${toolName}"]`);

        if (forceState === false || (forceState === undefined && panel.hasClass('open'))) {
            panel.removeClass('open');
            btn.removeClass('active');
            delete ns.state.openConfigPanels[toolName];
        } else {
            panel.addClass('open');
            btn.addClass('active');
            ns.state.openConfigPanels[toolName] = true;
            // Load roles if not already loaded
            if (ns.state.availableRoles.length === 0) {
                ns.loadAvailableRoles();
            }
        }
    };

    // Load available roles
    ns.loadAvailableRoles = function() {
        frappe.call({
            method: "pibiassistant.api.admin_api.get_available_roles",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.state.availableRoles = response.message.roles;
                }
            }
        });
    };

    // Show add role dialog
    ns.showAddRoleDialog = function(toolName) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        const existingRoles = (tool?.role_access || []).map(r => r.role);
        const availableRoles = ns.state.availableRoles.filter(r => !existingRoles.includes(r.name));

        if (availableRoles.length === 0) {
            frappe.show_alert({
                message: __('All available roles have been added'),
                indicator: 'orange'
            });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __('Add Role'),
            fields: [
                {
                    fieldname: 'role',
                    fieldtype: 'Select',
                    label: __('Role'),
                    options: availableRoles.map(r => r.name).join('\n'),
                    reqd: 1
                }
            ],
            primary_action_label: __('Add'),
            primary_action: function(values) {
                ns.addRole(toolName, values.role);
                dialog.hide();
            }
        });
        dialog.show();
    };

    // Add role to tool
    ns.addRole = function(toolName, role) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        if (!tool.role_access) {
            tool.role_access = [];
        }
        tool.role_access.push({ role: role, allow_access: 1 });

        // Re-render the role tags
        const container = $(`#role-tags-${toolName}`);
        const addBtn = container.find('.pa-add-role-btn');
        addBtn.before(`
            <span class="pa-role-tag" data-role="${role}">
                ${role}
                <button type="button" class="pa-role-remove-btn" aria-label="${__("Remove role")} ${frappe.utils.escape_html(role)}" data-tool="${toolName}" data-role="${role}">
                    <i class="fa fa-times remove-role" data-tool="${toolName}" data-role="${role}" aria-hidden="true"></i>
                </button>
            </span>
        `);

        // Re-attach remove handler
        container.find(`.remove-role[data-role="${role}"]`).off('click').on('click', function() {
            ns.removeRole(toolName, role);
        });
    };

    // Remove role from tool
    ns.removeRole = function(toolName, role) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        if (tool && tool.role_access) {
            tool.role_access = tool.role_access.filter(r => r.role !== role);
        }
        $(`#role-tags-${toolName} .pa-role-tag[data-role="${role}"]`).remove();
    };

    // Save tool configuration
    ns.saveToolConfig = function(toolName) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        const panel = $(`#config-panel-${toolName}`);

        const roleAccessMode = panel.find('.pa-role-mode-select').val();
        const category = panel.find('.pa-category-select').val();
        const roles = tool.role_access || [];

        // Show saving state
        const saveBtn = panel.find('.pa-config-save');
        saveBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

        // Update role access first
        frappe.call({
            method: "pibiassistant.api.admin_api.update_tool_role_access",
            args: {
                tool_name: toolName,
                role_access_mode: roleAccessMode,
                roles: roles
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    // Now update category
                    frappe.call({
                        method: "pibiassistant.api.admin_api.update_tool_category",
                        args: {
                            tool_name: toolName,
                            category: category,
                            override: true
                        },
                        callback: function(catResponse) {
                            if (catResponse.message && catResponse.message.success) {
                                frappe.show_alert({
                                    message: __('Tool configuration saved'),
                                    indicator: 'green'
                                });

                                // Update local data
                                tool.role_access_mode = roleAccessMode;
                                tool.category = category;

                                // Close panel and refresh
                                ns.toggleConfigPanel(toolName, false);
                                ns.loadToolsView();
                            } else {
                                frappe.show_alert({
                                    message: catResponse.message?.message || __('Failed to update category'),
                                    indicator: 'red'
                                });
                            }
                        },
                        always: function() {
                            saveBtn.prop('disabled', false).html(__('Save Changes'));
                        }
                    });
                } else {
                    frappe.show_alert({
                        message: response.message?.message || __('Failed to save configuration'),
                        indicator: 'red'
                    });
                    saveBtn.prop('disabled', false).html(__('Save Changes'));
                }
            },
            error: function() {
                frappe.show_alert({
                    message: __('Error saving configuration'),
                    indicator: 'red'
                });
                saveBtn.prop('disabled', false).html(__('Save Changes'));
            }
        });
    };

    // Toggle plugin enabled/disabled with race condition prevention
    ns.togglePlugin = function(pluginName, enabled) {
        const stateKey = `plugin_${pluginName}`;

        // Prevent duplicate toggle
        if (ns.state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

        // Update UI to show in-progress state
        const checkbox = $(`.pa-plugin-toggle[data-plugin="${pluginName}"]`);
        const originalState = !enabled;  // Original state is opposite of what we're trying to set
        checkbox.prop('disabled', true);
        checkbox.closest('.pa-plugin-item').addClass('toggle-in-progress');

        frappe.call({
            method: "pibiassistant.api.admin_api.toggle_plugin",
            args: {
                plugin_name: pluginName,
                enable: enabled
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Update stats only (not full reload to prevent visual glitch)
                    ns.loadStats();
                } else {
                    // Reset checkbox to original state on error
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({
                        message: response.message?.message || __('Unknown error'),
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                // Reset checkbox to original state on error
                checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: __('Error toggling plugin'),
                    indicator: 'red'
                });
            },
            always: function() {
                // Clear in-progress state
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.pa-plugin-item').removeClass('toggle-in-progress');
            }
        });
    };

    // Toggle individual tool enabled/disabled
    ns.toggleTool = function(toolName, enabled) {
        const stateKey = `tool_${toolName}`;

        // Prevent duplicate toggle
        if (ns.state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

        // Update UI to show in-progress state
        const checkbox = $(`.pa-tool-toggle[data-tool="${toolName}"]`);
        const originalState = !enabled;
        checkbox.prop('disabled', true);
        checkbox.closest('.pa-tool-item-detailed').addClass('toggle-in-progress');

        frappe.call({
            method: "pibiassistant.api.admin_api.toggle_tool",
            args: {
                tool_name: toolName,
                enabled: enabled ? 1 : 0
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Update local data
                    const tool = ns.toolsData.find(t => t.name === toolName);
                    if (tool) {
                        tool.tool_enabled = enabled;
                        tool.effectively_enabled = tool.plugin_enabled && enabled;
                    }
                    ns.loadStats();
                } else {
                    // Reset checkbox to original state on error
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({
                        message: response.message?.message || __('Unknown error'),
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                // Reset checkbox to original state on error
                checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: __('Error toggling tool'),
                    indicator: 'red'
                });
            },
            always: function() {
                // Clear in-progress state
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.pa-tool-item-detailed').removeClass('toggle-in-progress');
            }
        });
    };

    // Load recent activity
    ns.loadRecentActivity = function() {
        frappe.call({
            method: "pibiassistant.api.admin_api.get_usage_statistics",
            callback: function(response) {
                if (response.message && response.message.success) {
                    const activities = response.message.data.recent_activity || [];
                    if (activities.length > 0) {
                        const tableHtml = `
                            <table class="pa-table">
                                <thead>
                                    <tr>
                                        <th>${__("Action")}</th>
                                        <th>${__("Tool")}</th>
                                        <th>${__("User")}</th>
                                        <th>${__("Status")}</th>
                                        <th>${__("Time")}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${activities.slice(0, 5).map(a => {
                                        const ok = a.status === 'Success';
                                        const icon = ok ? 'fa-check-circle' : 'fa-times-circle';
                                        return `
                                        <tr>
                                            <td>${frappe.utils.escape_html(a.action)}</td>
                                            <td>${frappe.utils.escape_html(a.tool_name || '-')}</td>
                                            <td>${frappe.utils.escape_html(a.user)}</td>
                                            <td>
                                                <span class="indicator-pill ${ok ? 'green' : 'red'}">
                                                    <i class="fa ${icon}" aria-hidden="true"></i>
                                                    ${frappe.utils.escape_html(a.status)}
                                                </span>
                                            </td>
                                            <td style="color: var(--text-muted);">
                                                ${frappe.datetime.str_to_user(a.timestamp)}
                                            </td>
                                        </tr>
                                    `;}).join('')}
                                </tbody>
                            </table>
                        `;
                        $('#recent-activity').html(tableHtml);
                    } else {
                        $('#recent-activity').html(`
                            <div class="pa-empty-state pa-empty-state--compact">
                                <i class="fa fa-history" aria-hidden="true"></i>
                                <div class="pa-empty-title">${__("No activity yet")}</div>
                                <div class="pa-empty-subtitle">${__("Tool calls will appear here.")}</div>
                            </div>
                        `);
                    }
                }
            },
            error: function() {
                $('#recent-activity').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">' + __('Failed to load activity') + '</div>');
            }
        });
    };

    // Bulk toggle by category function
    // Count tools that match the current bulk filter (category + plugin)
    ns.countBulkScope = function(category, plugin) {
        if (!ns.toolsData) return 0;
        return ns.toolsData.filter(t => {
            if (category && t.category !== category) return false;
            if (plugin && t.plugin_name !== plugin) return false;
            return true;
        }).length;
    };

    // Update the "Will affect N tools" hint and toggle button disabled state.
    // Scope reads from the unified filter bar (category + plugin).
    ns.updateBulkScopeCount = function() {
        const category = $('#category-filter').val();
        const plugin = $('#plugin-filter').val();
        const n = ns.countBulkScope(category, plugin);
        const $hint = $('#bulk-scope-count');
        if (n === 0) {
            $hint.text(__('No tools match'));
        } else {
            $hint.text(n === 1 ? __('1 tool matches') : __('{0} tools match', [n]));
        }
        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', n === 0);
    };

    ns.bulkToggleByCategory = function(category, plugin, enabled) {
        const actionText = enabled ? 'enable' : 'disable';
        const n = ns.countBulkScope(category, plugin);

        const doBulk = function() {
            ns._performBulkToggle(category, plugin, enabled);
        };

        if (!enabled && n > 0) {
            frappe.confirm(
                n === 1 ? __('Disable 1 tool? Users will no longer be able to invoke it via MCP.') : __('Disable {0} tools? Users will no longer be able to invoke them via MCP.', [n]),
                doBulk
            );
        } else {
            doBulk();
        }
    };

    ns._performBulkToggle = function(category, plugin, enabled) {
        const actionText = enabled ? 'enable' : 'disable';

        // Disable buttons during operation
        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', true);
        const btn = enabled ? $('#bulk-enable-btn') : $('#bulk-disable-btn');
        const originalHtml = btn.html();
        btn.html(`<i class="fa fa-spinner fa-spin" aria-hidden="true"></i> ${enabled ? __('Enabling...') : __('Disabling...')}`);

        frappe.call({
            method: "pibiassistant.api.admin_api.bulk_toggle_tools_by_category",
            args: {
                category: category || null,
                plugin_name: plugin || null,
                enabled: enabled
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Refresh the tools list
                    ns.loadToolsView();
                    ns.loadStats();
                } else {
                    frappe.show_alert({
                        message: response.message?.message || (enabled ? __('Failed to enable tools') : __('Failed to disable tools')),
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                frappe.show_alert({
                    message: (enabled ? __('Error: Failed to enable tools') : __('Error: Failed to disable tools')),
                    indicator: 'red'
                });
            },
            always: function() {
                // Re-enable buttons (will be re-evaluated by updateBulkScopeCount)
                $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', false);
                if (typeof ns.updateBulkScopeCount === 'function') {
                    ns.updateBulkScopeCount();
                }
                btn.html(originalHtml);
            }
        });
    };

    // ── AIDA services ─────────────────────────────────────────────────
    // Shows which of the Chat / Convert / Voice APIs are configured and, on
    // demand (or on first load), whether each one answers.
    ns.loadAidaServices = function(showToast) {
        const esc = frappe.utils.escape_html;
        const $list = $('#pa-aida-services');
        frappe.call({
            method: "pibiassistant.pibiassistant_chat.api.aida.get_overview",
            callback: function(r) {
                const o = r.message || {};
                const model = [o.provider, o.model].filter(Boolean).join(' / ');
                $('#pa-aida-model').text(model ? __('Model: {0}', [model]) : __('No default model'));
                $('#analytics-model').text(o.model || '—');
                $list.empty();
                Object.keys(o.services || {}).forEach(function(name) {
                    const s = o.services[name];
                    $list.append(
                        `<li data-svc="${esc(name)} API"><span class="pa-status-pill ${s.configured ? '' : 'pa-status-pill--stopped'}">` +
                        `<span class="pa-status-dot" aria-hidden="true"></span> ${esc(name)}</span> ` +
                        `<span class="pa-sidebar-subtle svc-detail">${s.configured ? esc(s.url) : esc(__('Not configured'))}</span></li>`
                    );
                });
                frappe.call({
                    method: "pibiassistant.pibiassistant_chat.api.aida.test_connections",
                    callback: function(t) {
                        const res = t.message || {};
                        let failed = 0;
                        $list.find('li').each(function() {
                            const $li = $(this);
                            const st = res[$li.data('svc')];
                            if (!st) return;
                            const $pill = $li.find('.pa-status-pill');
                            $pill.toggleClass('pa-status-pill--running', !!st.ok)
                                 .toggleClass('pa-status-pill--stopped', !st.ok);
                            if (!st.ok) { failed++; $li.find('.svc-detail').text(st.error || __('No response')); }
                        });
                        if (showToast) {
                            frappe.show_alert({
                                message: failed ? __('{0} AIDA service(s) with problems', [failed]) : __('AIDA services operational'),
                                indicator: failed ? 'orange' : 'green'
                            });
                        }
                    }
                });
            },
            error: function() { $('#pa-aida-card').hide(); }
        });
    };
})();
