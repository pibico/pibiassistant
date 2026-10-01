import { qs, qsa, show, hide, debounce, on, toggleClass } from '../dom.js';
import { bindTablist } from './tablist.js';
import { loadPluginView } from './plugins-view.js';
import { loadToolsView } from './tools-view.js';
import { renderToolsList, clearToolFilters } from './tools-list.js';
import { updateBulkScopeCount, bulkToggleByCategory } from './bulk.js';
import { togglePlugin, toggleTool } from './toggles.js';
import {
  toggleConfigPanel, showAddRoleDialog, removeRole, saveToolConfig,
} from './config-panel.js';

function loadToolRegistry(ctx) {
  return ctx.state.viewMode === 'plugins' ? loadPluginView(ctx) : loadToolsView(ctx);
}

function activateViewTab(ctx, tabEl) {
  const view = tabEl.dataset.view;
  if (view === ctx.state.viewMode) return;
  for (const t of qsa('.pa-view-tab', ctx.root)) {
    t.classList.remove('active');
    t.setAttribute('aria-selected', 'false');
    t.setAttribute('tabindex', '-1');
  }
  tabEl.classList.add('active');
  tabEl.setAttribute('aria-selected', 'true');
  tabEl.setAttribute('tabindex', '0');
  ctx.state.viewMode = view;
  const bar = qs('#tools-filter-bar', ctx.root);
  if (view === 'tools') show(bar); else hide(bar);
  loadToolRegistry(ctx);
}

function wireViewTabs(ctx) {
  const list = qs('.pa-view-tabs', ctx.root);
  const activate = (tab) => activateViewTab(ctx, tab);
  ctx.scope.delegate(ctx.root, 'click', '.pa-view-tab', (e, tab) => activate(tab));
  ctx.scope.add(bindTablist(list, { tabSelector: '.pa-view-tab', onActivate: activate }));
}

function wireFilters(ctx) {
  const inTools = () => ctx.scope.alive && ctx.state.viewMode === 'tools';
  const search = qs('#tool-search', ctx.root);
  if (search) {
    const run = debounce(() => { if (inTools()) renderToolsList(ctx); }, 300);
    ctx.scope.add(on(search, 'input', run));
  }
  const rerender = () => {
    if (!inTools()) return;
    renderToolsList(ctx);
    updateBulkScopeCount(ctx);
  };
  ctx.scope.on(qs('#category-filter', ctx.root), 'change', rerender);
  ctx.scope.on(qs('#plugin-filter', ctx.root), 'change', rerender);

  const bulk = (enabled) => () => bulkToggleByCategory(
    ctx, qs('#category-filter', ctx.root).value, qs('#plugin-filter', ctx.root).value, enabled
  );
  ctx.scope.on(qs('#bulk-enable-btn', ctx.root), 'click', bulk(true));
  ctx.scope.on(qs('#bulk-disable-btn', ctx.root), 'click', bulk(false));
}

function wireRegistryEvents(ctx) {
  const host = qs('#tool-registry', ctx.root);
  if (!host) return;
  const d = (type, sel, fn) => ctx.scope.delegate(host, type, sel, fn);

  d('click', '.pa-desc-toggle', (e, btn) => {
    const wrap = btn.closest('.pa-tool-description-wrap');
    toggleClass(wrap, 'expanded');
    const expanded = wrap.classList.contains('expanded');
    btn.textContent = expanded ? __('Show less') : __('Show more');
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  });
  d('change', '.pa-plugin-toggle', (e, el) => togglePlugin(ctx, el.dataset.plugin, el.checked));
  d('change', '.pa-tool-toggle', (e, el) => toggleTool(ctx, el.dataset.tool, el.checked));
  d('click', '.pa-tool-settings-btn', (e, el) => toggleConfigPanel(ctx, el.dataset.tool));
  d('change', '.pa-role-mode-select', (e, sel) => {
    const section = qsa('.pa-roles-section', host).find((s) => s.dataset.tool === sel.dataset.tool);
    if (sel.value === 'Restrict to Listed Roles') show(section); else hide(section);
  });
  d('click', '.pa-add-role-btn', (e, el) => showAddRoleDialog(ctx, el.dataset.tool));
  d('click', '.pa-role-remove-btn', (e, el) => removeRole(ctx, el.dataset.tool, el.dataset.role));
  d('click', '.pa-config-cancel', (e, el) => {
    toggleConfigPanel(ctx, el.dataset.tool, false);
    renderToolsList(ctx);
  });
  d('click', '.pa-config-save', (e, el) => saveToolConfig(ctx, el.dataset.tool));
  d('click', '.pa-clear-filters-btn', () => clearToolFilters(ctx));
}

export function mountRegistry(root, ctx) {
  wireViewTabs(ctx);
  wireFilters(ctx);
  wireRegistryEvents(ctx);

  const offRefresh = ctx.bus.on('refresh', ({ scope } = {}) => {
    if (scope === 'initial' || scope === 'all') loadToolRegistry(ctx);
  });
  const offChat = ctx.bus.on('chat:status', (payload) => {
    if (payload && payload.userToggled) loadToolRegistry(ctx);
  });

  let done = false;
  return function unmount() {
    if (done) return;
    done = true;
    offRefresh();
    offChat();
  };
}
