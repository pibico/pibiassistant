import { qs, on, delegate, setHtml, debounce, escapeHtml as esc } from '../dom.js';
import { call, log } from '../api.js';
import { state } from '../state.js';
import { skeletonCards } from '../utils.js';
import { renderSafeMarkdown } from './sanitize.js';
import {
	emptyStateHtml, sharedChipsHtml, renderList, loadList, toggleStatus, togglePanel,
} from './items.js';


function config(ctx) {
	const root = ctx.root;
	return {
		kind: 'prompt',
		kindPlural: 'prompts',
		dataKey: 'promptsData',
		listKey: 'templates',
		listSel: '#prompt-templates-list',
		listMethod: 'pibiassistant.api.admin_api.get_prompt_templates_list',
		toggleMethod: 'pibiassistant.api.admin_api.toggle_prompt_template_status',
		toggleClass: 'pa-prompt-toggle',
		actionBtnClass: 'pa-prompt-preview-btn',
		actionIcon: 'ph-eye',
		get actionLabel() { return __('Preview template'); },
		get publishLabel() { return __('Publish prompt'); },
		docUrl: '/app/prompt-template/',
		idField: 'prompt_id',
		panelPrefix: 'prompt-preview-',
		skeleton: () => skeletonCards(3),
		loadingText: () => __('Loading preview...'),
		failText: () => __('Failed to load prompt templates'),
		loadErrorText: () => __('Error loading prompt templates'),
		toggleErrorText: () => __('Error toggling template status'),
		metaHtml: (t, lastUsed) => `
			${t.category ? `<span class="pa-meta-chip"><i class="ph ph-folder" aria-hidden="true"></i> ${esc(t.category)}</span>` : ''}
			${sharedChipsHtml(t, lastUsed)}`,
		matches: (t) => {
			const q = (qs('#prompt-search', root)?.value || '').toLowerCase();
			const status = qs('#prompt-status-filter', root)?.value;
			if (q && !(t.title || '').toLowerCase().includes(q) &&
				!(t.prompt_id || '').toLowerCase().includes(q)) return false;
			if (status && t.status !== status) return false;
			return true;
		},
		emptyHtml: () => emptyStateHtml({
			icon: 'ph-file-text',
			title: __('No prompt templates yet'),
			subtitle: __('Create a prompt template to expose it to MCP clients.'),
			action: `<a href="/app/prompt-template/new?status=Draft" class="btn btn-xs btn-primary">${esc(__('Create template'))}</a>`,
		}),
		noMatchHtml: () => emptyStateHtml({
			icon: 'ph-magnifying-glass',
			title: __('No templates match the current filters'),
			action: `<button type="button" class="btn btn-xs btn-default pa-clear-prompt-filters">${esc(__('Clear filters'))}</button>`,
		}),
	};
}

export function loadPromptTemplatesView(ctx) {
	return loadList(ctx, config(ctx));
}

export function renderPromptTemplatesList(ctx) {
	renderList(ctx, config(ctx));
}

export function togglePromptTemplateStatus(ctx, name, publish) {
	return toggleStatus(ctx, config(ctx), name, publish);
}

function previewHtml(d) {
	const args = d.arguments && d.arguments.length > 0
		? d.arguments.map((a) =>
			`<span class="pa-tool-badge" title="${esc(a.description || '')}">${esc(a.argument_name)}${a.is_required ? '*' : ''}</span>`
		).join(' ')
		: `<em class="pa-muted">${esc(__('No arguments'))}</em>`;
	return `
		<div class="pa-preview-meta">
			<span><strong class="pa-preview-label">${esc(__('Engine'))}:</strong> ${esc(d.rendering_engine || '')}</span>
			<span><strong class="pa-preview-label">${esc(__('Arguments'))}:</strong> ${args}</span>
		</div>
		<div class="pa-preview-content">${renderSafeMarkdown(d.template_content || '')}</div>`;
}

export function showTemplatePreview(ctx, name) {
	return togglePanel(ctx, config(ctx), name, async (panel) => {
		let d;
		try {
			d = await call('pibiassistant.api.admin_api.preview_prompt_template', { name }, { silent: true });
		} catch (err) {
			log.error('preview_prompt_template', err);
			if (ctx.scope.alive) setHtml(panel, `<div class="pa-error-block" role="alert">${esc(__('Error loading preview'))}</div>`);
			return;
		}
		if (!ctx.scope.alive) return;
		if (d && d.success) setHtml(panel, previewHtml(d));
		else setHtml(panel, `<div class="pa-error-block" role="alert">${esc(d?.message || __('Failed to load preview'))}</div>`);
	});
}

export function mountPrompts(root, ctx) {
	const offs = [];
	const rerender = () => {
		if (state.activeTab === 'prompts') renderPromptTemplatesList(ctx);
	};
	const search = qs('#prompt-search', root);
	const status = qs('#prompt-status-filter', root);
	if (search) offs.push(on(search, 'input', debounce(rerender, 300)));
	if (status) offs.push(on(status, 'change', rerender));

	const list = qs('#prompt-templates-list', root);
	if (list) {
		offs.push(delegate(list, 'change', '.pa-prompt-toggle', (e, el) => {
			togglePromptTemplateStatus(ctx, el.dataset.name, el.checked);
		}));
		offs.push(delegate(list, 'click', '.pa-prompt-preview-btn', (e, el) => {
			showTemplatePreview(ctx, el.dataset.name);
		}));
		offs.push(delegate(list, 'click', '.pa-clear-prompt-filters', () => {
			if (search) search.value = '';
			if (status) status.value = '';
			renderPromptTemplatesList(ctx);
		}));
	}
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
