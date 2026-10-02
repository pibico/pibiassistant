import { qs, setHtml } from '../dom.js';
import { call, log } from '../api.js';

const esc = (s) => frappe.utils.escape_html(String(s ?? ''));

function rowHtml(a) {
	const ok = a.status === 'Success';
	const icon = ok ? 'ph-check-circle' : 'ph-x-circle';
	const tool = a.tool_name && a.tool_name !== a.action ? ` · ${esc(a.tool_name)}` : '';
	return `
		<li class="pa-act">
			<div class="pa-act__top">
				<span class="pa-act__name">${esc(a.action)}</span>
				<span class="indicator-pill ${ok ? 'green' : 'red'}">
					<i class="ph ${icon}" aria-hidden="true"></i>
					${esc(a.status)}
				</span>
			</div>
			<div class="pa-act__meta">${esc(a.user)}${tool} · ${esc(frappe.datetime.str_to_user(a.timestamp))}</div>
		</li>`;
}

function tableHtml(activities) {
	return `<ul class="pa-act-list">${activities.slice(0, 5).map(rowHtml).join('')}</ul>`;
}

function emptyHtml() {
	return `
		<div class="pa-empty-state pa-empty-state--compact">
			<i class="ph ph-clock-counter-clockwise" aria-hidden="true"></i>
			<div class="pa-empty-title">${esc(__('No activity yet'))}</div>
			<div class="pa-empty-subtitle">${esc(__('Tool calls will appear here.'))}</div>
		</div>`;
}

function failureHtml() {
	return `<div role="alert" class="pa-error-block">${esc(__('Failed to load activity'))}</div>`;
}

export async function loadRecentActivity(ctx) {
	const host = qs('#recent-activity', ctx.root);
	let msg;
	try {
		msg = await call('pibiassistant.api.admin_api.get_usage_statistics', {}, { silent: true });
	} catch (err) {
		log.warn('get_usage_statistics', err);
		if (ctx.scope.alive) {
			setHtml(host, failureHtml());
		}
		return;
	}
	if (!ctx.scope.alive) return;
	if (!msg || !msg.success) {
		setHtml(host, failureHtml());
		return;
	}
	const activities = msg.data?.recent_activity || [];
	setHtml(host, activities.length ? tableHtml(activities) : emptyHtml());
}

export function mountActivityCard(root, ctx) {
	const off = ctx.bus.on('refresh', (p) => {
		if (p?.scope) loadRecentActivity(ctx);
	});
	return function unmount() {
		off();
	};
}
