import { qs, qsa, setHtml, hide } from '../dom.js';
import { toolCardHtml } from './tool-card.js';
import { registryHost } from './lookup.js';

export function readFilters(ctx) {
  return {
    searchTerm: (qs('#tool-search', ctx.root)?.value || '').toLowerCase(),
    category: qs('#category-filter', ctx.root)?.value || '',
    plugin: qs('#plugin-filter', ctx.root)?.value || '',
  };
}

function matches(tool, { searchTerm, category, plugin }) {
  if (searchTerm && !tool.name.toLowerCase().includes(searchTerm) &&
      !(tool.description || '').toLowerCase().includes(searchTerm)) return false;
  if (category) {
    const toolCategory = tool.category === 'dangerous' ? 'privileged' : tool.category;
    const filterCategory = category === 'dangerous' ? 'privileged' : category;
    if (toolCategory !== filterCategory) return false;
  }
  if (plugin && tool.plugin_name !== plugin) return false;
  return true;
}

function emptyHtml(zeroData) {
  if (zeroData) {
    return `
                    <div class="pa-empty-state">
                        <i class="fa fa-wrench" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__('No tools registered')}</div>
                        <div class="pa-empty-subtitle">${__('Enable a plugin in the Plugins tab to register tools.')}</div>
                    </div>
                `;
  }
  return `
                    <div class="pa-empty-state">
                        <i class="fa fa-search" aria-hidden="true"></i>
                        <div class="pa-empty-title">${__('No tools match the current filters')}</div>
                        <button type="button" class="btn btn-xs btn-default pa-clear-filters-btn">${__('Clear filters')}</button>
                    </div>
                `;
}

export function clearToolFilters(ctx) {
  for (const id of ['#tool-search', '#category-filter', '#plugin-filter']) {
    const el = qs(id, ctx.root);
    if (el) el.value = '';
  }
  renderToolsList(ctx);
}

export function renderToolsList(ctx) {
  const host = registryHost(ctx);
  if (!host) return;
  const filters = readFilters(ctx);
  const all = ctx.state.toolsData || [];
  const filtered = all.filter((t) => matches(t, filters));

  if (filtered.length === 0) {
    setHtml(host, emptyHtml(all.length === 0));
    return;
  }

  setHtml(host, filtered.map((tool) => toolCardHtml(tool, {
    isToggling: ctx.state.toggleInProgress[`tool_${tool.name}`],
    isPanelOpen: ctx.state.openConfigPanels[tool.name],
    searchTerm: filters.searchTerm,
  })).join(''));

  for (const wrap of qsa('.pa-tool-description-wrap', host)) {
    const desc = wrap.querySelector('.pa-tool-description');
    if (desc && desc.scrollHeight <= desc.clientHeight + 2) hide(wrap.querySelector('.pa-desc-toggle'));
  }
}
