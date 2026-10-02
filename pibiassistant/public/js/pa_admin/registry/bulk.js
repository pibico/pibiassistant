import { qs, setText, setHtml } from '../dom.js';
import { call } from '../api.js';
import * as toast from '../toast.js';
import { loadToolsView } from './tools-view.js';

export function countBulkScope(ctx, category, plugin) {
  const tools = ctx.state.toolsData || [];
  return tools.filter((t) => {
    if (category && t.category !== category) return false;
    if (plugin && t.plugin_name !== plugin) return false;
    return true;
  }).length;
}

function bulkButtons(ctx) {
  return [qs('#bulk-enable-btn', ctx.root), qs('#bulk-disable-btn', ctx.root)];
}

export function updateBulkScopeCount(ctx) {
  const n = countBulkScope(ctx, qs('#category-filter', ctx.root)?.value, qs('#plugin-filter', ctx.root)?.value);
  const hint = qs('#bulk-scope-count', ctx.root);
  if (n === 0) setText(hint, __('No tools match'));
  else setText(hint, n === 1 ? __('1 tool matches') : __('{0} tools match', [n]));
  for (const b of bulkButtons(ctx)) if (b) b.disabled = n === 0;
}

async function performBulkToggle(ctx, category, plugin, enabled) {
  const [enableBtn, disableBtn] = bulkButtons(ctx);
  for (const b of [enableBtn, disableBtn]) if (b) b.disabled = true;
  const btn = enabled ? enableBtn : disableBtn;
  const originalHtml = btn?.innerHTML;
  setHtml(btn, `<i class="ph ph-spinner ph-spin" aria-hidden="true"></i> ${enabled ? __('Enabling...') : __('Disabling...')}`);

  try {
    const res = await call('pibiassistant.api.admin_api.bulk_toggle_tools_by_category', {
      category: category || null,
      plugin_name: plugin || null,
      enabled,
    }, { silent: true });
    if (res && res.success) {
      toast.alert(res.message, enabled ? 'green' : 'orange');
      loadToolsView(ctx);
      ctx.bus.emit('tools:changed', {});
    } else {
      toast.error(res?.message || (enabled ? __('Failed to enable tools') : __('Failed to disable tools')));
    }
  } catch (e) {
    toast.error(enabled ? __('Error: Failed to enable tools') : __('Error: Failed to disable tools'));
  } finally {
    if (ctx.scope.alive) {
      for (const b of [enableBtn, disableBtn]) if (b) b.disabled = false;
      updateBulkScopeCount(ctx);
      if (btn) setHtml(btn, originalHtml);
    }
  }
}

export function bulkToggleByCategory(ctx, category, plugin, enabled) {
  const n = countBulkScope(ctx, category, plugin);
  const doBulk = () => performBulkToggle(ctx, category, plugin, enabled);
  if (!enabled && n > 0) {
    toast.confirm(
      n === 1
        ? __('Disable 1 tool? Users will no longer be able to invoke it via MCP.')
        : __('Disable {0} tools? Users will no longer be able to invoke them via MCP.', [n]),
      doBulk,
      null,
      { title: __('Disable tools'), confirmLabel: __('Disable') }
    );
  } else {
    doBulk();
  }
}
