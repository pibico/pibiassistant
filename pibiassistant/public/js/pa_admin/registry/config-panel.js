import { setHtml } from '../dom.js';
import { call } from '../api.js';
import * as toast from '../toast.js';
import { byData, findTool, registryHost } from './lookup.js';
import { roleTagHtml } from './tool-card.js';
import { loadToolsView } from './tools-view.js';

export function toggleConfigPanel(ctx, toolName, force) {
  const panel = document.getElementById(`config-panel-${toolName}`);
  const btn = byData(registryHost(ctx), '.pa-tool-settings-btn', 'tool', toolName);
  const isOpen = panel?.classList.contains('open');

  if (force === false || (force === undefined && isOpen)) {
    panel?.classList.remove('open');
    btn?.classList.remove('active');
    btn?.setAttribute('aria-expanded', 'false');
    delete ctx.state.openConfigPanels[toolName];
  } else {
    panel?.classList.add('open');
    btn?.classList.add('active');
    btn?.setAttribute('aria-expanded', 'true');
    ctx.state.openConfigPanels[toolName] = true;
    if (ctx.state.availableRoles.length === 0) loadAvailableRoles(ctx);
  }
}

function focusSoon(ctx, find) {
  setTimeout(() => {
    if (!ctx.scope.alive) return;
    const el = find();
    if (el && el.isConnected && typeof el.focus === 'function') el.focus();
  }, 0);
}

const addRoleBtn = (toolName) => document.getElementById(`role-tags-${toolName}`)?.querySelector('.pa-add-role-btn');
const settingsBtn = (ctx, toolName) => byData(registryHost(ctx), '.pa-tool-settings-btn', 'tool', toolName);

export async function loadAvailableRoles(ctx) {
  try {
    const res = await call('pibiassistant.api.admin_api.get_available_roles', {}, { silent: true });
    if (res && res.success) ctx.state.availableRoles = res.roles;
  } catch (e) {
    // roles stay empty; the add-role dialog reports that nothing is available
  }
}

export function addRole(ctx, toolName, role) {
  const tool = findTool(ctx, toolName);
  if (!tool) return;
  if (!tool.role_access) tool.role_access = [];
  tool.role_access.push({ role, allow_access: 1 });
  const addBtn = document.getElementById(`role-tags-${toolName}`)?.querySelector('.pa-add-role-btn');
  addBtn?.insertAdjacentHTML('beforebegin', roleTagHtml(toolName, role));
  focusSoon(ctx, () => addRoleBtn(toolName));
}

export function removeRole(ctx, toolName, role) {
  const tool = findTool(ctx, toolName);
  if (tool && tool.role_access) tool.role_access = tool.role_access.filter((r) => r.role !== role);
  const container = document.getElementById(`role-tags-${toolName}`);
  byData(container, '.pa-role-tag', 'role', role)?.remove();
  focusSoon(ctx, () => addRoleBtn(toolName));
}

export function showAddRoleDialog(ctx, toolName) {
  const tool = findTool(ctx, toolName);
  const existing = (tool?.role_access || []).map((r) => r.role);
  const available = ctx.state.availableRoles.filter((r) => !existing.includes(r.name));
  if (available.length === 0) {
    toast.warning(__('All available roles have been added'));
    return;
  }
  const opener = document.activeElement;
  const dialog = new frappe.ui.Dialog({
    title: __('Add Role'),
    fields: [{
      fieldname: 'role',
      fieldtype: 'Select',
      label: __('Role'),
      options: available.map((r) => r.name).join('\n'),
      reqd: 1,
    }],
    primary_action_label: __('Add'),
    primary_action(values) {
      addRole(ctx, toolName, values.role);
      dialog.hide();
    },
  });
  ctx.scope.add(() => { try { dialog.hide(); } catch (e) { /* already disposed */ } });
  dialog.onhide = () => {
    focusSoon(ctx, () => (opener && opener.isConnected ? opener : addRoleBtn(toolName)));
  };
  dialog.show();
  const modal = dialog.$wrapper?.get(0);
  if (modal) {
    const title = modal.querySelector('.modal-title');
    if (title) {
      title.id = title.id || `pa-add-role-title-${Date.now()}`;
      modal.setAttribute('aria-labelledby', title.id);
    }
    modal.addEventListener('keydown', (e) => {
      if (e.key !== 'Tab') return;
      const items = Array.from(modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
        .filter((el) => !el.disabled && el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }
}

export async function saveToolConfig(ctx, toolName) {
  const tool = findTool(ctx, toolName);
  const panel = document.getElementById(`config-panel-${toolName}`);
  if (!tool || !panel) return;
  const mode = panel.querySelector('.pa-role-mode-select').value;
  const category = panel.querySelector('.pa-category-select').value;
  const saveBtn = panel.querySelector('.pa-config-save');
  saveBtn.disabled = true;
  setHtml(saveBtn, `<i class="fa fa-spinner fa-spin"></i> ${__('Saving...')}`);
  const restore = () => {
    if (!ctx.scope.alive) return;
    saveBtn.disabled = false;
    setHtml(saveBtn, __('Save Changes'));
  };

  try {
    const res = await call('pibiassistant.api.admin_api.update_tool_role_access', {
      tool_name: toolName,
      role_access_mode: mode,
      roles: tool.role_access || [],
    }, { silent: true });
    if (!(res && res.success)) {
      toast.error(res?.message || __('Failed to save configuration'));
      return;
    }
    const cat = await call('pibiassistant.api.admin_api.update_tool_category', {
      tool_name: toolName,
      category,
      override: true,
    }, { silent: true });
    if (cat && cat.success) {
      toast.success(__('Tool configuration saved'));
      tool.role_access_mode = mode;
      tool.category = category;
      if (ctx.scope.alive) {
        toggleConfigPanel(ctx, toolName, false);
        await loadToolsView(ctx);
        focusSoon(ctx, () => settingsBtn(ctx, toolName));
      }
    } else {
      toast.error(cat?.message || __('Failed to update category'));
    }
  } catch (e) {
    toast.error(__('Error saving configuration'));
  } finally {
    restore();
  }
}
