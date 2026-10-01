import { qs, setHtml, escapeHtml as esc } from '../dom.js';
import { call } from '../api.js';
import { hasToggleInProgress } from '../state.js';
import { registryHost, failedHtml, withTimeout } from './lookup.js';

function pluginItemHtml(plugin, isToggling) {
  return `
                            <div class="pa-plugin-item ${isToggling ? 'toggle-in-progress' : ''}">
                                <div class="pa-plugin-header">
                                    <div class="pa-plugin-info">
                                        <div class="pa-plugin-name">
                                            <i class="fa fa-cube"></i>
                                            ${esc(plugin.name)}
                                        </div>
                                    </div>
                                    <div>
                                        <label class="switch" style="margin: 0;">
                                            <input type="checkbox" class="pa-plugin-toggle"
                                                   data-plugin="${esc(plugin.plugin_id)}"
                                                   aria-label="${__('Enable plugin')} ${esc(plugin.name)}"
                                                   ${plugin.enabled ? 'checked' : ''}
                                                   ${isToggling ? 'disabled' : ''}>
                                            <span class="slider round"></span>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        `;
}

export function renderPlugins(host, plugins, toggling) {
  if (!host) return;
  if (plugins.length === 0) {
    setHtml(host, `
                            <div class="pa-empty-state">
                                <i class="fa fa-cube" aria-hidden="true"></i>
                                <div class="pa-empty-title">${__('No plugins installed')}</div>
                                <div class="pa-empty-subtitle">${__('Install plugins to start registering tools with the MCP server.')}</div>
                            </div>
                        `);
    return;
  }
  setHtml(host, plugins.map((p) => pluginItemHtml(p, toggling[`plugin_${p.plugin_id}`])).join(''));
}

export async function loadPluginView(ctx) {
  if (hasToggleInProgress()) return;
  let res;
  try {
    res = await withTimeout(call('pibiassistant.api.admin_api.get_plugin_stats', {}, { silent: true }));
  } catch (e) {
    if (ctx.scope.alive) setHtml(registryHost(ctx), failedHtml(__('Failed to load plugins')));
    return;
  }
  if (!ctx.scope.alive) return;
  if (!res || !res.plugins) {
    setHtml(registryHost(ctx), failedHtml(__('Failed to load plugins')));
    return;
  }
  renderPlugins(qs('#tool-registry', ctx.root), res.plugins, ctx.state.toggleInProgress);
  ctx.bus.emit('tools:loaded', { view: 'plugins', count: res.plugins.length });
}
