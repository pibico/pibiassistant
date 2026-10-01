import { qs, qsa, h, setHtml } from '../dom.js';
import { call } from '../api.js';
import { hasToggleInProgress } from '../state.js';
import { renderToolsList } from './tools-list.js';
import { updateBulkScopeCount } from './bulk.js';
import { registryHost, failedHtml, withTimeout } from './lookup.js';

function pluginLabel(p) {
  return p.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function populatePluginFilter(ctx) {
  const select = qs('#plugin-filter', ctx.root);
  if (!select) return;
  qsa('option', select).slice(1).forEach((o) => o.remove());
  const plugins = [...new Set(ctx.state.toolsData.map((t) => t.plugin_name))];
  for (const p of plugins) select.append(h('option', { value: p }, pluginLabel(p)));
}

export async function loadToolsView(ctx) {
  if (hasToggleInProgress()) return;
  let res;
  try {
    res = await withTimeout(call('pibiassistant.api.admin_api.get_tool_configurations', {}, { silent: true }));
  } catch (e) {
    res = null;
  }
  if (!ctx.scope.alive) return;
  if (res && res.success) {
    ctx.state.toolsData = res.tools;
    populatePluginFilter(ctx);
    renderToolsList(ctx);
    updateBulkScopeCount(ctx);
    ctx.bus.emit('tools:loaded', { view: 'tools', count: res.tools.length });
  } else {
    setHtml(registryHost(ctx), failedHtml(__('Failed to load tools')));
  }
}
