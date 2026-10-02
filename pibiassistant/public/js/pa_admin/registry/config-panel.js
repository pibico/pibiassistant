import { setHtml, delegate, show, hide, qsa, escapeHtml as esc } from '../dom.js';
import { call } from '../api.js';
import * as toast from '../toast.js';
import { openPanel } from '../panel.js';
import { byData, findTool, registryHost } from './lookup.js';
import { roleTagHtml, configPanelHtml } from './tool-card.js';
import { loadToolsView } from './tools-view.js';


// Edits to the allowed roles live in a draft until Save, so Cancel discards them.
let active = null;

const settingsBtn = (ctx, toolName) => byData(registryHost(ctx), '.pa-tool-settings-btn', 'tool', toolName);
const addRoleBtn = (toolName) => document.getElementById(`role-tags-${toolName}`)?.querySelector('.pa-add-role-btn');

function focusSoon(ctx, find) {
  setTimeout(() => {
    if (!ctx.scope.alive) return;
    const el = find();
    if (el && el.isConnected && typeof el.focus === 'function') el.focus();
  }, 0);
}

export function toggleConfigPanel(ctx, toolName, force) {
  const isOpen = active && active.toolName === toolName;
  if (force === false || (force === undefined && isOpen)) {
    active?.panel.close();
    return;
  }
  if (isOpen) return;
  const tool = findTool(ctx, toolName);
  if (!tool) return;
  active?.panel.close('replaced', { immediate: true });
  const draft = (tool.role_access || []).map((r) => ({ ...r }));
  const btn = settingsBtn(ctx, toolName);
  btn?.classList.add('active');
  btn?.setAttribute('aria-expanded', 'true');
  ctx.state.openConfigPanels[toolName] = true;
  if (ctx.state.availableRoles.length === 0) loadAvailableRoles(ctx);
  const panel = openPanel({
    title: __('Configure role access'),
    root: ctx.root,
    body: configPanelHtml(tool, draft),
    returnFocus: () => settingsBtn(ctx, toolName),
    onClose: () => {
      const b = settingsBtn(ctx, toolName);
      b?.classList.remove('active');
      b?.setAttribute('aria-expanded', 'false');
      delete ctx.state.openConfigPanels[toolName];
      if (active && active.toolName === toolName) active = null;
    },
  });
  active = { toolName, draft, panel };
  wirePanel(ctx, toolName, panel.bodyEl);
}

function wirePanel(ctx, toolName, body) {
  const d = (type, sel, fn) => ctx.scope.add(delegate(body, type, sel, fn));
  d('change', '.pa-role-mode-select', (e, sel) => {
    const section = qsa('.pa-roles-section', body)[0];
    if (sel.value === 'Restrict to Listed Roles') show(section); else hide(section);
  });
  d('click', '.pa-add-role-btn', () => showAddRoleDialog(ctx, toolName));
  d('click', '.pa-role-remove-btn', (e, el) => removeRole(ctx, toolName, el.dataset.role));
  d('click', '.pa-config-cancel', () => toggleConfigPanel(ctx, toolName, false));
  d('click', '.pa-config-save', () => saveToolConfig(ctx, toolName));
}

export async function loadAvailableRoles(ctx) {
  try {
    const res = await call('pibiassistant.api.admin_api.get_available_roles', {}, { silent: true });
    if (res && res.success) ctx.state.availableRoles = res.roles;
  } catch (e) {
    // roles stay empty; the add-role panel reports that nothing is available
  }
}

export function addRole(ctx, toolName, role) {
  if (!active || active.toolName !== toolName) return;
  active.draft.push({ role, allow_access: 1 });
  addRoleBtn(toolName)?.insertAdjacentHTML('beforebegin', roleTagHtml(toolName, role));
  focusSoon(ctx, () => addRoleBtn(toolName));
}

export function removeRole(ctx, toolName, role) {
  if (!active || active.toolName !== toolName) return;
  active.draft = active.draft.filter((r) => r.role !== role);
  const container = document.getElementById(`role-tags-${toolName}`);
  byData(container, '.pa-role-tag', 'role', role)?.remove();
  focusSoon(ctx, () => addRoleBtn(toolName));
}

export function showAddRoleDialog(ctx, toolName) {
  if (!active || active.toolName !== toolName) return;
  const existing = active.draft.map((r) => r.role);
  const available = ctx.state.availableRoles.filter((r) => !existing.includes(r.name));
  if (available.length === 0) {
    toast.warning(__('All available roles have been added'));
    return;
  }
  const body = document.createElement('div');
  body.innerHTML = `
    <label class="pa-config-label" for="pa-add-role-select">${esc(__('Role'))}</label>
    <select class="pa-config-select" id="pa-add-role-select">
      ${available.map((r) => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('')}
    </select>`;
  const footer = document.createElement('div');
  footer.className = 'pa-panel-actions';
  footer.innerHTML = `
    <button type="button" class="btn btn-default pa-panel-cancel">${esc(__('Cancel'))}</button>
    <button type="button" class="btn btn-primary pa-panel-confirm">${esc(__('Add'))}</button>`;
  const panel = openPanel({
    title: __('Add Role'),
    root: ctx.root,
    body,
    footer,
    returnFocus: () => addRoleBtn(toolName),
  });
  footer.querySelector('.pa-panel-cancel').addEventListener('click', () => panel.close('cancel'));
  footer.querySelector('.pa-panel-confirm').addEventListener('click', () => {
    const role = body.querySelector('select').value;
    panel.close('confirm', { immediate: true });
    addRole(ctx, toolName, role);
  });
}

export async function saveToolConfig(ctx, toolName) {
  const tool = findTool(ctx, toolName);
  const panelEl = document.getElementById(`config-panel-${toolName}`);
  if (!tool || !panelEl || !active) return;
  const mode = panelEl.querySelector('.pa-role-mode-select').value;
  const category = panelEl.querySelector('.pa-category-select').value;
  const roles = active.draft;
  const saveBtn = panelEl.querySelector('.pa-config-save');
  saveBtn.disabled = true;
  setHtml(saveBtn, `<i class="ph ph-spinner ph-spin" aria-hidden="true"></i> ${__('Saving...')}`);
  const restore = () => {
    if (!ctx.scope.alive) return;
    saveBtn.disabled = false;
    setHtml(saveBtn, __('Save Changes'));
  };

  try {
    const res = await call('pibiassistant.api.admin_api.update_tool_role_access', {
      tool_name: toolName,
      role_access_mode: mode,
      roles,
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
      tool.role_access = roles;
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
