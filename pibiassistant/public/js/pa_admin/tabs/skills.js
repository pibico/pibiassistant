import { qs, on, delegate, setHtml, debounce } from '../dom.js';
import { call, log } from '../api.js';
import { state } from '../state.js';
import { skeletonCards } from '../utils.js';
import { renderSafeMarkdown } from './sanitize.js';
import {
	emptyStateHtml, sharedChipsHtml, renderList, loadList, toggleStatus, togglePanel,
} from './items.js';

const esc = (s) => frappe.utils.escape_html(String(s ?? ''));

function config(ctx) {
	const root = ctx.root;
	return {
		kind: 'skill',
		kindPlural: 'skills',
		dataKey: 'skillsData',
		listKey: 'skills',
		listSel: '#skills-list',
		listMethod: 'pibiassistant.api.admin_api.get_skills_list',
		toggleMethod: 'pibiassistant.api.admin_api.toggle_skill_status',
		toggleClass: 'pa-skill-toggle',
		actionBtnClass: 'pa-skill-content-btn',
		actionIcon: 'fa-book',
		actionAriaColon: true,
		get actionLabel() { return __('View skill content'); },
		get publishLabel() { return __('Publish skill'); },
		docUrl: '/app/pa-skill/',
		idField: 'skill_id',
		panelPrefix: 'skill-content-',
		skeleton: () => skeletonCards(3),
		loadingText: () => __('Loading content...'),
		failText: () => __('Failed to load skills'),
		loadErrorText: () => __('Error loading skills'),
		toggleErrorText: () => __('Error toggling skill status'),
		metaHtml: (s, lastUsed) => `
			<span class="pa-meta-chip">${esc(s.skill_type || '')}</span>
			${s.linked_tool ? `<span class="pa-meta-chip"><i class="fa fa-wrench"></i> ${esc(s.linked_tool)}</span>` : ''}
			${sharedChipsHtml(s, lastUsed)}`,
		matches: (s) => {
			const q = (qs('#skill-search', root)?.value || '').toLowerCase();
			const type = qs('#skill-type-filter', root)?.value;
			const status = qs('#skill-status-filter', root)?.value;
			if (q && !(s.title || '').toLowerCase().includes(q) &&
				!(s.skill_id || '').toLowerCase().includes(q)) return false;
			if (type && s.skill_type !== type) return false;
			if (status && s.status !== status) return false;
			return true;
		},
		emptyHtml: () => emptyStateHtml({
			icon: 'fa-graduation-cap',
			title: __('No skills yet'),
			subtitle: __('Skills are reusable workflows or tool-usage patterns exposed to MCP clients.'),
			action: `<a href="/app/pa-skill/new?status=Draft" class="btn btn-xs btn-primary">${esc(__('Create skill'))}</a>`,
		}),
		noMatchHtml: () => emptyStateHtml({
			icon: 'fa-search',
			title: __('No skills match the current filters'),
			action: `<button type="button" class="btn btn-xs btn-default pa-clear-skill-filters">${esc(__('Clear filters'))}</button>`,
		}),
	};
}

export function loadSkillsView(ctx) {
	return loadList(ctx, config(ctx));
}

export function renderSkillsList(ctx) {
	renderList(ctx, config(ctx));
}

export function toggleSkillStatus(ctx, name, publish) {
	return toggleStatus(ctx, config(ctx), name, publish);
}

export function showSkillContent(ctx, name) {
	return togglePanel(ctx, config(ctx), name, async (panel) => {
		let msg;
		try {
			msg = await call('frappe.client.get_value', {
				doctype: 'PA Skill', filters: { name }, fieldname: 'content',
			}, { silent: true });
		} catch (err) {
			log.error('PA Skill get_value', err);
			if (ctx.scope.alive) setHtml(panel, `<div style="color:var(--red-500);">${esc(__('Error loading content'))}</div>`);
			return;
		}
		if (!ctx.scope.alive) return;
		if (msg && msg.content) setHtml(panel, `<div style="font-size:13px;">${renderSafeMarkdown(msg.content)}</div>`);
		else setHtml(panel, `<div style="color:var(--text-muted);">${esc(__('No content available'))}</div>`);
	});
}

export function mountSkills(root, ctx) {
	const offs = [];
	const rerender = () => {
		if (state.activeTab === 'skills') renderSkillsList(ctx);
	};
	const search = qs('#skill-search', root);
	const type = qs('#skill-type-filter', root);
	const status = qs('#skill-status-filter', root);
	if (search) offs.push(on(search, 'input', debounce(rerender, 300)));
	if (type) offs.push(on(type, 'change', rerender));
	if (status) offs.push(on(status, 'change', rerender));

	const list = qs('#skills-list', root);
	if (list) {
		offs.push(delegate(list, 'change', '.pa-skill-toggle', (e, el) => {
			toggleSkillStatus(ctx, el.dataset.name, el.checked);
		}));
		offs.push(delegate(list, 'click', '.pa-skill-content-btn', (e, el) => {
			showSkillContent(ctx, el.dataset.name);
		}));
		offs.push(delegate(list, 'click', '.pa-clear-skill-filters', () => {
			[search, type, status].forEach((el) => { if (el) el.value = ''; });
			renderSkillsList(ctx);
		}));
	}
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
