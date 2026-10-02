import { escapeHtml as esc } from '../dom.js';
import { highlight } from '../utils.js';

export function roleTagHtml(toolName, role) {
  const t = esc(toolName);
  const r = esc(role);
  return `<span class="pa-role-tag" data-role="${r}">
                    ${r}
                    <button type="button" class="pa-role-remove-btn" aria-label="${__('Remove role')} ${r}" data-tool="${t}" data-role="${r}">
                        <i class="ph ph-x remove-role" data-tool="${t}" data-role="${r}" aria-hidden="true"></i>
                    </button>
                </span>`;
}

export function toolCardHtml(tool, { isToggling, isPanelOpen, searchTerm }) {
  const name = esc(tool.name);
  const display = esc(tool.display_name);
  const pluginDisabled = !tool.plugin_enabled;
  const titleHtml = highlight(tool.display_name, searchTerm);
  const descHtml = highlight(tool.description || __('No description available'), searchTerm);

  return `
                <div class="pa-tool-item-detailed ${isToggling ? 'toggle-in-progress' : ''} ${pluginDisabled ? 'pa-disabled-overlay' : ''}" data-tool-name="${name}">
                    <div class="pa-tool-header">
                        <div class="pa-tool-title">
                            ${titleHtml}
                            <span class="pa-category-badge ${esc(tool.category)}">${esc(__(tool.category_label))}</span>
                        </div>
                        <div class="pa-tool-actions">
                            <button class="pa-tool-settings-btn ${isPanelOpen ? 'active' : ''}"
                                    data-tool="${name}"
                                    aria-label="${__('Configure role access')}: ${display}"
                                    aria-expanded="${isPanelOpen ? 'true' : 'false'}"
                                    title="${__('Configure role access')}">
                                <i class="ph ph-gear" aria-hidden="true"></i>
                            </button>
                            <label class="switch">
                                <input type="checkbox" class="pa-tool-toggle"
                                       data-tool="${name}"
                                       aria-label="${__('Enable tool')} ${display}"
                                       ${tool.tool_enabled ? 'checked' : ''}
                                       ${isToggling || pluginDisabled ? 'disabled' : ''}>
                                <span class="slider round"></span>
                            </label>
                        </div>
                    </div>
                    <div class="pa-tool-description-wrap">
                        <div class="pa-tool-description">${descHtml}</div>
                        <button type="button" class="pa-desc-toggle" aria-expanded="false">${__('Show more')}</button>
                    </div>
                    <div class="pa-tool-footer">
                        <span class="pa-tool-badge">${esc(__(tool.plugin_display_name))}</span>
                        ${pluginDisabled ? '<span class="pa-plugin-disabled-notice"><i class="ph ph-warning-circle" aria-hidden="true"></i> ' + __('Plugin disabled') + '</span>' : ''}
                        ${tool.role_access_mode !== 'Allow All' ? '<span class="pa-tool-badge pa-tool-badge--lock"><i class="ph ph-lock" aria-hidden="true"></i> ' + __('Role restricted') + '</span>' : ''}
                    </div>
                </div>
            `;
}

export function configPanelHtml(tool, roles) {
  const name = esc(tool.name);
  const display = esc(tool.display_name);
  const restricted = tool.role_access_mode === 'Restrict to Listed Roles';
  const isPriv = tool.category === 'privileged' || tool.category === 'dangerous';
  const roleTags = roles.map((r) => roleTagHtml(tool.name, r.role)).join('');
  return `
<div class="pa-tool-config-panel open" id="config-panel-${name}">
  <p class="pa-config-tool">${display}</p>
    <div class="pa-config-row">
        <div class="pa-config-group">
            <label class="pa-config-label">${__('Role Access Mode')}</label>
            <select class="pa-config-select pa-role-mode-select" data-tool="${name}">
                <option value="Allow All" ${tool.role_access_mode === 'Allow All' ? 'selected' : ''}>${__('Allow All Users')}</option>
                <option value="Restrict to Listed Roles" ${restricted ? 'selected' : ''}>${__('Restrict to Listed Roles')}</option>
            </select>
        </div>
        <div class="pa-config-group">
            <label class="pa-config-label">${__('Category')}</label>
            <select class="pa-config-select pa-category-select" data-tool="${name}">
                <option value="read_only" ${tool.category === 'read_only' ? 'selected' : ''}>${__('Read Only')}</option>
                <option value="write" ${tool.category === 'write' ? 'selected' : ''}>${__('Write')}</option>
                <option value="read_write" ${tool.category === 'read_write' ? 'selected' : ''}>${__('Read & Write')}</option>
                <option value="privileged" ${isPriv ? 'selected' : ''}>${__('Privileged')}</option>
            </select>
        </div>
    </div>
    <div class="pa-config-row pa-roles-section" data-tool="${name}" style="${restricted ? '' : 'display: none;'}">
        <div class="pa-config-group">
            <label class="pa-config-label">${__('Allowed Roles')}</label>
            <div class="pa-role-tags" id="role-tags-${name}">
                ${roleTags}
                <button type="button" class="pa-add-role-btn" data-tool="${name}" aria-label="${__('Add role')}: ${display}">
                    <i class="ph ph-plus" aria-hidden="true"></i> ${__('Add Role')}
                </button>
            </div>
        </div>
    </div>
    <div class="pa-config-actions">
        <button class="btn btn-xs btn-default pa-config-cancel" data-tool="${name}">${__('Cancel')}</button>
        <button class="btn btn-xs btn-primary pa-config-save" data-tool="${name}">${__('Save Changes')}</button>
    </div>
</div>`;
}
