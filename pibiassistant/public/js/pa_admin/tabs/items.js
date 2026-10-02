import { qs, qsa, setHtml, addClass, removeClass } from '../dom.js';
import { call, log } from '../api.js';
import { state, beginToggle, endToggle } from '../state.js';
import { loadStats } from './counts.js';
import { openPanel } from '../panel.js';

const esc = (s) => frappe.utils.escape_html(String(s ?? ''));

export function errorBlockHtml(text) {
	return `<div role="alert" class="pa-error-block">${esc(text)}</div>`;
}

export function emptyStateHtml({ icon, title, subtitle, action }) {
	return `
		<div class="pa-empty-state">
			<i class="ph ${icon}" aria-hidden="true"></i>
			<div class="pa-empty-title">${esc(title)}</div>
			${subtitle ? `<div class="pa-empty-subtitle">${esc(subtitle)}</div>` : ''}
			${action || ''}
		</div>`;
}

export function findCard(root, name) {
	return qsa('.pa-item-card', root).find((c) => c.dataset.name === name) || null;
}

export function sharedChipsHtml(item, lastUsed) {
	return `
		<span class="pa-meta-chip"><i class="ph ph-eye" aria-hidden="true"></i> ${esc(__(item.visibility || 'Private'))}</span>
		${item.is_system ? `<span class="pa-meta-chip system-chip">${esc(__('System'))}</span>` : ''}
		<span class="pa-meta-chip">${esc(__('Used {0}x', [item.use_count || 0]))}</span>
		<span class="pa-meta-chip"><i class="ph ph-clock" aria-hidden="true"></i> ${esc(lastUsed)}</span>`;
}

export function cardHtml(cfg, item) {
	const isToggling = state.toggleInProgress[`${cfg.kind}_${item.name}`];
	const isPublished = item.status === 'Published';
	const statusClass = (item.status || 'draft').toLowerCase();
	const lastUsed = item.last_used ? frappe.datetime.str_to_user(item.last_used) : __('Never');
	const title = esc(item.title);
	return `
		<div class="pa-item-card ${isToggling ? 'toggle-in-progress' : ''}" data-name="${esc(item.name)}">
			<div class="pa-item-header">
				<div class="pa-item-title">
					${title}
					<span class="pa-status-badge ${esc(statusClass)}">${esc(item.status)}</span>
				</div>
				<div class="pa-item-actions">
					<button class="pa-tool-settings-btn ${cfg.actionBtnClass}"
							data-name="${esc(item.name)}"
							aria-label="${esc(cfg.actionLabel)}${cfg.actionAriaColon ? ':' : ''} ${title}"
							title="${esc(cfg.actionLabel)}">
						<i class="ph ${cfg.actionIcon}" aria-hidden="true"></i>
					</button>
					<a href="${cfg.docUrl}${encodeURIComponent(item.name)}" target="_blank"
					   class="pa-tool-settings-btn"
					   aria-label="${esc(__('Open in DocType'))}: ${title}"
					   title="${esc(__('Open in DocType'))}">
						<i class="ph ph-arrow-square-out" aria-hidden="true"></i>
					</a>
					<label class="switch" title="${esc(isPublished ? __('Click to unpublish') : __('Click to publish'))}">
						<input type="checkbox" class="${cfg.toggleClass}"
							   data-name="${esc(item.name)}"
							   aria-label="${esc(cfg.publishLabel)} ${title}"
							   ${isPublished ? 'checked' : ''}
							   ${isToggling ? 'disabled' : ''}>
						<span class="slider round"></span>
					</label>
				</div>
			</div>
			<div class="pa-item-subtitle">${esc(item[cfg.idField] || item.name)}</div>
			<div class="pa-item-meta">${cfg.metaHtml(item, lastUsed)}</div>
		</div>`;
}

export function renderList(ctx, cfg) {
	const host = qs(cfg.listSel, ctx.root);
	const data = state[cfg.dataKey] || [];
	const filtered = data.filter(cfg.matches);
	if (filtered.length === 0) {
		setHtml(host, data.length === 0 ? cfg.emptyHtml() : cfg.noMatchHtml());
		return;
	}
	setHtml(host, filtered.map((item) => cardHtml(cfg, item)).join(''));
}

export async function loadList(ctx, cfg) {
	const host = qs(cfg.listSel, ctx.root);
	setHtml(host, cfg.skeleton());
	let msg;
	try {
		msg = await call(cfg.listMethod, {}, { silent: true });
	} catch (err) {
		log.error(cfg.listMethod, err);
		if (ctx.scope.alive) setHtml(host, errorBlockHtml(cfg.loadErrorText()));
		return;
	}
	if (!ctx.scope.alive) return;
	if (msg && msg.success) {
		state[cfg.dataKey] = msg[cfg.listKey];
		renderList(ctx, cfg);
		ctx.bus.emit(`${cfg.kindPlural}:loaded`, { count: msg.total ?? state[cfg.dataKey].length });
	} else {
		setHtml(host, errorBlockHtml(cfg.failText()));
	}
}

export async function toggleStatus(ctx, cfg, name, publish) {
	const key = `${cfg.kind}_${name}`;
	if (!beginToggle(key)) return;
	const card = findCard(ctx.root, name);
	const checkbox = qs(`.${cfg.toggleClass}`, card);
	if (checkbox) checkbox.disabled = true;
	addClass(card, 'toggle-in-progress');

	const revert = (text) => {
		if (!ctx.scope.alive) return;
		if (checkbox) { checkbox.checked = !publish; checkbox.disabled = false; }
		removeClass(card, 'toggle-in-progress');
		ctx.toast.error(text);
	};

	let msg;
	try {
		msg = await call(cfg.toggleMethod, { name, publish: publish ? 1 : 0 }, { silent: true });
	} catch (err) {
		log.error(cfg.toggleMethod, err);
		endToggle(key);
		revert(cfg.toggleErrorText());
		return;
	}
	endToggle(key);
	if (!ctx.scope.alive) return;
	if (msg && msg.success) {
		publish ? ctx.toast.success(msg.message) : ctx.toast.warning(msg.message);
		const item = (state[cfg.dataKey] || []).find((x) => x.name === name);
		if (item) item.status = msg.new_status;
		renderList(ctx, cfg);
		const again = qs(`.${cfg.toggleClass}`, findCard(ctx.root, name));
		if (again) again.focus();
		loadStats(ctx);
	} else {
		revert(msg?.message || __('Unknown error'));
	}
}

export async function togglePanel(ctx, cfg, name, fill) {
	const item = (state[cfg.dataKey] || []).find((x) => x.name === name);
	const btn = () => qs(`.${cfg.actionBtnClass}`, findCard(ctx.root, name));
	const panel = openPanel({
		title: item?.title || name,
		root: ctx.root,
		body: `<div class="pa-muted"><i class="ph ph-spinner ph-spin" aria-hidden="true"></i> ${esc(cfg.loadingText())}</div>`,
		returnFocus: btn,
		onClose: () => removeClass(btn(), 'active'),
	});
	addClass(btn(), 'active');
	await fill(panel.bodyEl);
}
