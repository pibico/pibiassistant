import { call } from '../api.js';
import { beginToggle, endToggle } from '../state.js';
import * as toast from '../toast.js';
import { byData, registryHost } from './lookup.js';

async function runToggle(ctx, { key, selector, dataKey, name, itemSelector, enabled, method, args, errorText, onSuccess }) {
  if (!beginToggle(key)) return;
  const checkbox = byData(registryHost(ctx), selector, dataKey, name);
  const item = checkbox?.closest(itemSelector);
  if (checkbox) checkbox.disabled = true;
  item?.classList.add('toggle-in-progress');

  const revert = () => { if (checkbox) checkbox.checked = !enabled; };
  try {
    const res = await call(method, args, { silent: true });
    if (res && res.success) {
      toast.alert(res.message, enabled ? 'green' : 'orange');
      onSuccess?.();
      ctx.bus.emit('tools:changed', {});
    } else {
      revert();
      toast.error(res?.message || __('Unknown error'));
    }
  } catch (e) {
    revert();
    toast.error(errorText);
  } finally {
    endToggle(key);
    if (checkbox) checkbox.disabled = false;
    item?.classList.remove('toggle-in-progress');
  }
}

export function togglePlugin(ctx, pluginId, enabled) {
  return runToggle(ctx, {
    key: `plugin_${pluginId}`,
    selector: '.pa-plugin-toggle',
    dataKey: 'plugin',
    name: pluginId,
    itemSelector: '.pa-plugin-item',
    enabled,
    method: 'pibiassistant.api.admin_api.toggle_plugin',
    args: { plugin_name: pluginId, enable: enabled },
    errorText: __('Error toggling plugin'),
  });
}

export function toggleTool(ctx, toolName, enabled) {
  return runToggle(ctx, {
    key: `tool_${toolName}`,
    selector: '.pa-tool-toggle',
    dataKey: 'tool',
    name: toolName,
    itemSelector: '.pa-tool-item-detailed',
    enabled,
    method: 'pibiassistant.api.admin_api.toggle_tool',
    args: { tool_name: toolName, enabled: enabled ? 1 : 0 },
    errorText: __('Error toggling tool'),
    onSuccess: () => {
      const tool = ctx.state.toolsData.find((t) => t.name === toolName);
      if (tool) {
        tool.tool_enabled = enabled;
        tool.effectively_enabled = tool.plugin_enabled && enabled;
      }
    },
  });
}
