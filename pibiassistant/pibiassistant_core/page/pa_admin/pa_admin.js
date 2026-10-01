frappe.pages['pa-admin'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('AIDA Admin'),
        single_column: true
    });

    // Initialize shared namespace before loading submodules
    frappe.pa_admin = {
        page: page,
        state: {
            toggleInProgress: {},
            refreshInProgress: false,
            autoRefreshEnabled: true,
            viewMode: 'plugins',
            activeTab: 'tools',
            availableRoles: [],
            openConfigPanels: {},
            promptsData: [],
            skillsData: [],
        },
    };

    const ns = frappe.pa_admin;

    // Load CSS and inject HTML, then load JS submodules
    frappe.require("/assets/pibiassistant/css/pa_admin.css");

    page.main.html(`
        <div class="pa-admin-container">

            <!-- Page header strip: server status + refresh ticker -->
            <div class="pa-page-header">
                <div class="pa-page-title">
                    <span id="server-status-icon" class="pa-status-indicator"></span>
                    <span id="server-status-text">AIDA</span>
                    <span id="server-status-pill" class="pa-status-pill" role="status" aria-live="polite"></span>
                </div>
                <div class="pa-page-actions">
                    <span id="pa-last-refreshed" class="pa-last-refreshed" aria-live="polite"></span>
                    <button class="btn btn-sm btn-default" id="refresh-all" aria-label="${__('Refresh dashboard')}">
                        <i class="fa fa-refresh" aria-hidden="true"></i>
                    </button>
                    <button class="btn btn-sm btn-primary" id="toggle-server">
                        <span id="toggle-server-text">${__("Loading...")}</span>
                    </button>
                </div>
            </div>

            <!-- Two-column body: left = registry, right = sidebar -->
            <div class="pa-two-col">

                <!-- LEFT: registry card with tabs (counts in pills) -->
                <div class="pa-card pa-registry-card">

                    <!-- Top-Level Tab Navigation -->
                    <div class="pa-top-tabs" role="tablist" aria-label="${__('AIDA Admin sections')}">
                        <button class="pa-top-tab active" data-tab="tools" role="tab" id="tab-tools" aria-selected="true" aria-controls="tab-panel-tools" tabindex="0">
                            <i class="fa fa-wrench" aria-hidden="true"></i>
                            ${__("Tools")}
                            <span class="pa-tab-count" id="tab-count-tools" aria-hidden="true">–</span>
                        </button>
                        <button class="pa-top-tab" data-tab="prompts" role="tab" id="tab-prompts" aria-selected="false" aria-controls="tab-panel-prompts" tabindex="-1">
                            <i class="fa fa-file-text-o" aria-hidden="true"></i>
                            ${__("Prompts")}
                            <span class="pa-tab-count" id="tab-count-prompts" aria-hidden="true">–</span>
                        </button>
                        <button class="pa-top-tab" data-tab="skills" role="tab" id="tab-skills" aria-selected="false" aria-controls="tab-panel-skills" tabindex="-1">
                            <i class="fa fa-graduation-cap" aria-hidden="true"></i>
                            ${__("Skills")}
                            <span class="pa-tab-count" id="tab-count-skills" aria-hidden="true">–</span>
                        </button>
                    </div>

                    <!-- TOOLS TAB PANEL -->
                    <div class="pa-tab-panel active" id="tab-panel-tools" role="tabpanel" aria-labelledby="tab-tools" tabindex="0">

                        <!-- View Mode Tabs -->
                        <div class="pa-view-tabs" role="tablist" aria-label="${__('Tool registry view mode')}">
                            <button type="button" class="pa-view-tab active" data-view="plugins" role="tab" aria-selected="true" tabindex="0">
                                <i class="fa fa-cube" aria-hidden="true"></i> ${__("Plugins")}
                            </button>
                            <button type="button" class="pa-view-tab" data-view="tools" role="tab" aria-selected="false" tabindex="-1">
                                <i class="fa fa-wrench" aria-hidden="true"></i> ${__("Individual Tools")}
                            </button>
                        </div>

                        <!-- Filter + Bulk Actions Bar (shown in tools view) -->
                        <div class="pa-filter-bar" id="tools-filter-bar" style="display: none;">
                            <input type="text" class="pa-filter-input" id="tool-search"
                                   placeholder="${__("Search tools...")}" aria-label="${__('Search tools')}">
                            <select class="pa-filter-select" id="category-filter" aria-label="${__('Filter by category')}">
                                <option value="">${__("All Categories")}</option>
                                <option value="read_only">${__("Read Only")}</option>
                                <option value="write">${__("Write")}</option>
                                <option value="read_write">${__("Read & Write")}</option>
                                <option value="privileged">${__("Privileged")}</option>
                            </select>
                            <select class="pa-filter-select" id="plugin-filter" aria-label="${__('Filter by plugin')}">
                                <option value="">${__("All Plugins")}</option>
                            </select>
                            <span id="bulk-scope-count" class="pa-bulk-scope" aria-live="polite"></span>
                            <button class="btn btn-xs btn-success" id="bulk-enable-btn" disabled>
                                <i class="fa fa-check" aria-hidden="true"></i> <span class="pa-btn-label">${__("Enable matching")}</span>
                            </button>
                            <button class="btn btn-xs btn-warning" id="bulk-disable-btn" disabled>
                                <i class="fa fa-times" aria-hidden="true"></i> <span class="pa-btn-label">${__("Disable matching")}</span>
                            </button>
                        </div>

                        <div id="tool-registry" class="pa-scroll-area">
                            <div class="pa-skeleton-wrap"><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div></div>
                        </div>
                    </div>

                    <!-- PROMPT TEMPLATES TAB PANEL -->
                    <div class="pa-tab-panel" id="tab-panel-prompts" role="tabpanel" aria-labelledby="tab-prompts" tabindex="0">
                        <div class="pa-filter-bar">
                            <input type="text" class="pa-filter-input" id="prompt-search"
                                   placeholder="${__("Search templates...")}" aria-label="${__('Search templates')}">
                            <select class="pa-filter-select" id="prompt-status-filter" aria-label="${__('Filter by status')}">
                                <option value="">${__("All Statuses")}</option>
                                <option value="Published">${__("Published")}</option>
                                <option value="Draft">${__("Draft")}</option>
                                <option value="Deprecated">${__("Deprecated")}</option>
                                <option value="Archived">${__("Archived")}</option>
                            </select>
                        </div>
                        <div id="prompt-templates-list" class="pa-scroll-area">
                            <div class="pa-skeleton-wrap"><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div></div>
                        </div>
                    </div>

                    <!-- SKILLS TAB PANEL -->
                    <div class="pa-tab-panel" id="tab-panel-skills" role="tabpanel" aria-labelledby="tab-skills" tabindex="0">
                        <div class="pa-filter-bar">
                            <input type="text" class="pa-filter-input" id="skill-search"
                                   placeholder="${__("Search skills...")}" aria-label="${__('Search skills')}">
                            <select class="pa-filter-select" id="skill-type-filter" aria-label="${__('Filter by type')}">
                                <option value="">${__("All Types")}</option>
                                <option value="Tool Usage">${__("Tool Usage")}</option>
                                <option value="Workflow">${__("Workflow")}</option>
                            </select>
                            <select class="pa-filter-select" id="skill-status-filter" aria-label="${__('Filter by status')}">
                                <option value="">${__("All Statuses")}</option>
                                <option value="Published">${__("Published")}</option>
                                <option value="Draft">${__("Draft")}</option>
                                <option value="Deprecated">${__("Deprecated")}</option>
                            </select>
                        </div>
                        <div id="skills-list" class="pa-scroll-area">
                            <div class="pa-skeleton-wrap"><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div><div class="pa-skeleton-card"><div class="pa-skeleton-line pa-skeleton-line--title"></div><div class="pa-skeleton-line pa-skeleton-line--body"></div></div></div>
                        </div>
                    </div>

                </div>

                <!-- RIGHT: sticky sidebar with status, chat, analytics, actions -->
                <aside class="pa-sidebar" aria-label="${__('Operations')}">

                    <!-- System / MCP card -->
                    <div class="pa-card pa-sidebar-card">
                        <div class="pa-sidebar-row">
                            <span class="pa-sidebar-label">${__("MCP endpoint")}</span>
                            <button type="button" class="btn btn-xs btn-default pa-copy-endpoint" id="copy-endpoint" aria-label="${__('Copy MCP endpoint URL')}" title="${__('Copy endpoint URL')}">
                                <i class="fa fa-copy" aria-hidden="true"></i>
                            </button>
                        </div>
                        <div class="pa-endpoint-url pa-endpoint-compact" id="pa-mcp-endpoint">${__("Loading...")}</div>
                        <div class="pa-sidebar-actions">
                            <button class="btn btn-xs btn-default" id="open-settings">
                                <i class="fa fa-cog" aria-hidden="true"></i> ${__("Settings")}
                            </button>
                        </div>
                    </div>

                    <!-- AIDA services card -->
                    <div class="pa-card pa-sidebar-card" id="pa-aida-card">
                        <div class="pa-sidebar-row">
                            <div class="pa-sidebar-title">
                                <i class="fa fa-plug" aria-hidden="true"></i> ${__("AIDA services")}
                            </div>
                        </div>
                        <ul class="pa-quick-list" id="pa-aida-services">
                            <li><span class="pa-sidebar-subtle">${__("Loading...")}</span></li>
                        </ul>
                        <div class="pa-sidebar-subtle" id="pa-aida-model"></div>
                        <div class="pa-sidebar-actions">
                            <button class="btn btn-xs btn-default" id="test-aida">
                                <i class="fa fa-refresh" aria-hidden="true"></i> ${__("Test connections")}
                            </button>
                            <button class="btn btn-xs btn-primary" id="configure-aida">
                                <i class="fa fa-cog" aria-hidden="true"></i> ${__("Configure")}
                            </button>
                        </div>
                    </div>

                    <!-- PA Chat card -->
                    <div class="pa-card pa-sidebar-card" id="pa-chat-card">
                        <div class="pa-sidebar-row">
                            <div class="pa-sidebar-title">
                                <i class="fa fa-comments" aria-hidden="true"></i>
                                ${__("AIDA Chat")}
                                <span id="pa-chat-status-pill" class="pa-status-pill" role="status" aria-live="polite"></span>
                            </div>
                        </div>
                        <div class="pa-sidebar-subtle">${__("Widget on Desk")} · <code>/aida</code> SPA</div>
                        <div class="pa-sidebar-actions">
                            <button class="btn btn-xs btn-primary" id="toggle-pa-chat">
                                <span id="toggle-pa-chat-text">${__("Loading...")}</span>
                            </button>
                            <a href="/aida" target="_blank" rel="noopener" class="btn btn-xs btn-default" id="open-aida" aria-label="${__('Open AIDA in a new tab')}">
                                <i class="fa fa-external-link" aria-hidden="true"></i>
                            </a>
                        </div>
                    </div>

                    <!-- Chat Analytics card (hidden when chat is disabled) -->
                    <div class="pa-card pa-sidebar-card" id="pa-chat-analytics-card" style="display: none;">
                        <div class="pa-sidebar-row">
                            <div class="pa-sidebar-title">
                                <i class="fa fa-line-chart" aria-hidden="true"></i> ${__("Chat usage")}
                            </div>
                        </div>
                        <div class="pa-analytics-grid">
                            <div class="pa-analytics-cell">
                                <div class="pa-analytics-label">${__("This month")}</div>
                                <div class="pa-analytics-value" id="analytics-monthly">–</div>
                            </div>
                            <div class="pa-analytics-cell">
                                <div class="pa-analytics-label">${__("All time")}</div>
                                <div class="pa-analytics-value" id="analytics-total">–</div>
                            </div>
                            <div class="pa-analytics-cell">
                                <div class="pa-analytics-label">${__("Active users")}</div>
                                <div class="pa-analytics-value" id="analytics-users">–</div>
                            </div>
                            <div class="pa-analytics-cell">
                                <div class="pa-analytics-label">${__("Model")}</div>
                                <div class="pa-analytics-value" id="analytics-model" style="font-size:13px;word-break:break-all;">–</div>
                            </div>
                        </div>
                        <div class="pa-analytics-spark" id="analytics-spark" aria-label="${__('Daily messages, last 30 days')}"></div>
                    </div>

                    <!-- Quick Actions card -->
                    <div class="pa-card pa-sidebar-card">
                        <div class="pa-sidebar-row">
                            <div class="pa-sidebar-title"><i class="fa fa-bolt" aria-hidden="true"></i> ${__("Quick actions")}</div>
                        </div>
                        <ul class="pa-quick-list">
                            <li><a href="/app/assistant-audit-log"><i class="fa fa-history" aria-hidden="true"></i> ${__("Audit log")}</a></li>
                            <li><a href="/app/assistant-core-settings"><i class="fa fa-cogs" aria-hidden="true"></i> ${__("AIDA Settings")}</a></li>
                            <li><a href="/aida" target="_blank" rel="noopener"><i class="fa fa-external-link" aria-hidden="true"></i> ${__("Open AIDA")}</a></li>
                        </ul>
                    </div>

                    <!-- Recent Activity card -->
                    <div class="pa-card pa-sidebar-card">
                        <div class="pa-sidebar-row">
                            <div class="pa-sidebar-title"><i class="fa fa-history" aria-hidden="true"></i> ${__("Recent activity")}</div>
                            <a href="/app/assistant-audit-log" class="pa-view-all">${__("View all")} <i class="fa fa-arrow-right" aria-hidden="true"></i></a>
                        </div>
                        <div id="recent-activity" class="pa-activity-list">
                            <div style="padding: 12px 0; text-align: center; color: var(--text-muted);">
                                <i class="fa fa-spinner fa-spin"></i> ${__("Loading...")}
                            </div>
                        </div>
                    </div>

                </aside>

            </div>
        </div>
    `);

    // Load JS submodules, then wire event handlers and start data loading
    frappe.require([
        "/assets/pibiassistant/js/pa_admin_utils.js",
        "/assets/pibiassistant/js/pa_admin_tools.js",
        "/assets/pibiassistant/js/pa_admin_prompts.js",
        "/assets/pibiassistant/js/pa_admin_skills.js"
    ]).then(function() {

        // =====================================================================
        // Event handlers
        // =====================================================================

        // Server toggle
        $('#toggle-server').on('click', ns.toggleServer);
        $('#open-settings').on('click', function() {
            frappe.set_route('Form', 'PA Core Settings');
        });

        // PA Chat toggle
        $('#toggle-pa-chat').on('click', ns.toggleFacChat);

        // AIDA services
        $('#configure-aida').on('click', function() {
            frappe.set_route('Form', 'PA Core Settings');
        });
        $('#test-aida').on('click', function() { ns.loadAidaServices(true); });

        // Copy MCP endpoint URL to clipboard
        $('#copy-endpoint').on('click', function() {
            const url = $('#pa-mcp-endpoint').text().trim();
            if (!url || url === __('Loading...')) return;
            frappe.utils.copy_to_clipboard(url);
        });

        // Global refresh — pulls everything visible on the page
        $('#refresh-all').on('click', function() {
            ns.state.lastRefreshedAt = new Date();
            if (typeof ns.updateLastRefreshedLabel === 'function') ns.updateLastRefreshedLabel();
            ns.loadServerStatus();
            ns.loadChatStatus();
            ns.loadAidaServices();
            ns.loadStats();
            ns.loadRecentActivity();
            ns.loadToolRegistry();
            if (typeof ns.loadChatAnalytics === 'function') ns.loadChatAnalytics();
        });

        // View mode tab handlers (Plugins / Individual Tools)
        ns.activateViewTab = function($tab) {
            const viewMode = $tab.data('view');
            if (viewMode === ns.state.viewMode) return;

            $('.pa-view-tab')
                .removeClass('active')
                .attr({ 'aria-selected': 'false', tabindex: '-1' });
            $tab
                .addClass('active')
                .attr({ 'aria-selected': 'true', tabindex: '0' });

            ns.state.viewMode = viewMode;

            if (viewMode === 'tools') {
                $('#tools-filter-bar').show();
            } else {
                $('#tools-filter-bar').hide();
            }

            ns.loadToolRegistry();
        };

        $('.pa-view-tab').on('click', function() {
            ns.activateViewTab($(this));
        });

        // Filter handlers (for tools view)
        $('#tool-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.viewMode === 'tools') {
                ns.renderToolsList();
            }
        }, 300));

        $('#category-filter, #plugin-filter').on('change', function() {
            if (ns.state.viewMode === 'tools') {
                ns.renderToolsList();
                if (typeof ns.updateBulkScopeCount === 'function') {
                    ns.updateBulkScopeCount();
                }
            }
        });

        // Bulk action button handlers (scoped to current filter bar selection)
        $('#bulk-enable-btn').on('click', function() {
            const category = $('#category-filter').val();
            const plugin = $('#plugin-filter').val();
            ns.bulkToggleByCategory(category, plugin, true);
        });

        $('#bulk-disable-btn').on('click', function() {
            const category = $('#category-filter').val();
            const plugin = $('#plugin-filter').val();
            ns.bulkToggleByCategory(category, plugin, false);
        });

        // Top-level tab switching
        ns.switchTab = function(tabName) {
            if (ns.state.activeTab === tabName) return;
            ns.state.activeTab = tabName;

            $('.pa-top-tab')
                .removeClass('active')
                .attr({ 'aria-selected': 'false', tabindex: '-1' });
            $(`.pa-top-tab[data-tab="${tabName}"]`)
                .addClass('active')
                .attr({ 'aria-selected': 'true', tabindex: '0' });

            $('.pa-tab-panel').removeClass('active');
            $(`#tab-panel-${tabName}`).addClass('active');

            if (tabName === 'prompts' && ns.state.promptsData.length === 0) {
                ns.loadPromptTemplatesView();
            } else if (tabName === 'skills' && ns.state.skillsData.length === 0) {
                ns.loadSkillsView();
            }
        };

        $('.pa-top-tab').on('click', function() {
            ns.switchTab($(this).data('tab'));
        });

        // Arrow-key navigation for tab lists (WAI-ARIA pattern)
        function handleTabKeydown(e, $tabs, activate) {
            const key = e.key;
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return;
            e.preventDefault();
            const count = $tabs.length;
            const currentIndex = $tabs.index(e.currentTarget);
            let nextIndex = currentIndex;
            if (key === 'ArrowRight') nextIndex = (currentIndex + 1) % count;
            else if (key === 'ArrowLeft') nextIndex = (currentIndex - 1 + count) % count;
            else if (key === 'Home') nextIndex = 0;
            else if (key === 'End') nextIndex = count - 1;
            const $next = $tabs.eq(nextIndex);
            $next.trigger('focus');
            activate($next);
        }

        $('.pa-top-tabs').on('keydown', '.pa-top-tab', function(e) {
            handleTabKeydown(e, $('.pa-top-tab'), function($tab) {
                ns.switchTab($tab.data('tab'));
            });
        });

        $('.pa-view-tabs').on('keydown', '.pa-view-tab', function(e) {
            handleTabKeydown(e, $('.pa-view-tab'), function($tab) {
                ns.activateViewTab($tab);
            });
        });

        // Prompt Templates filter handlers
        $('#prompt-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.activeTab === 'prompts') ns.renderPromptTemplatesList();
        }, 300));

        $('#prompt-status-filter').on('change', function() {
            if (ns.state.activeTab === 'prompts') ns.renderPromptTemplatesList();
        });

        $('#refresh-prompts').on('click', ns.loadPromptTemplatesView);

        // Skills filter handlers
        $('#skill-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.activeTab === 'skills') ns.renderSkillsList();
        }, 300));

        $('#skill-type-filter, #skill-status-filter').on('change', function() {
            if (ns.state.activeTab === 'skills') ns.renderSkillsList();
        });

        $('#refresh-skills').on('click', ns.loadSkillsView);

        // =====================================================================
        // Initial data load
        // =====================================================================
        ns.state.lastRefreshedAt = new Date();
        ns.loadServerStatus();
        ns.loadChatStatus();
        ns.loadAidaServices();
        ns.loadStats();
        ns.loadToolRegistry();
        ns.loadRecentActivity();
        if (typeof ns.loadChatAnalytics === 'function') ns.loadChatAnalytics();

        // "Updated Xs ago" ticker — cheap, local-only
        ns.updateLastRefreshedLabel = function() {
            const ts = ns.state.lastRefreshedAt;
            if (!ts) return;
            const seconds = Math.max(0, Math.round((Date.now() - ts.getTime()) / 1000));
            let label;
            if (seconds < 5) label = __('Updated just now');
            else if (seconds < 60) label = __('Updated {0}s ago', [seconds]);
            else label = __('Updated {0}m ago', [Math.round(seconds / 60)]);
            $('#pa-last-refreshed').text(label);
        };
        setInterval(ns.updateLastRefreshedLabel, 5000);
        ns.updateLastRefreshedLabel();

        // Auto-refresh every 30 seconds (respects autoRefreshEnabled flag)
        setInterval(function() {
            if (!ns.state.autoRefreshEnabled || Object.keys(ns.state.toggleInProgress).length > 0) {
                return;
            }

            ns.state.lastRefreshedAt = new Date();
            ns.updateLastRefreshedLabel();
            ns.loadServerStatus();
            ns.loadStats();
            ns.loadRecentActivity();
            if (typeof ns.loadChatAnalytics === 'function') ns.loadChatAnalytics();
            // Note: We intentionally don't auto-refresh loadToolRegistry() here
            // to avoid interfering with user toggle interactions
        }, 30000);
    });
};
