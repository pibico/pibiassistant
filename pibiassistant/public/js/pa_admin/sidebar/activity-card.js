import { qs, setHtml } from '../dom.js';
import { call, log } from '../api.js';

const esc = (s) => frappe.utils.escape_html(String(s ?? ''));

function rowHtml(a) {
	const ok = a.status === 'Success';
	const icon = ok ? 'fa-check-circle' : 'fa-times-circle';
	return `
		<tr>
			<td>${esc(a.action)}</td>
			<td>${esc(a.tool_name || '-')}</td>
			<td>${esc(a.user)}</td>
			<td>
				<span class="indicator-pill ${ok ? 'green' : 'red'}">
					<i class="fa ${icon}" aria-hidden="true"></i>
					${esc(a.status)}
				</span>
			</td>
			<td style="color: var(--text-muted);">
				${esc(frappe.datetime.str_to_user(a.timestamp))}
			</td>
		</tr>`;
}

function tableHtml(activities) {
	return `
		<table class="pa-table">
			<thead>
				<tr>
					<th>${esc(__('Action'))}</th>
					<th>${esc(__('Tool'))}</th>
					<th>${esc(__('User'))}</th>
					<th>${esc(__('Status'))}</th>
					<th>${esc(__('Time'))}</th>
				</tr>
			</thead>
			<tbody>${activities.slice(0, 5).map(rowHtml).join('')}</tbody>
		</table>`;
}

function emptyHtml() {
	return `
		<div class="pa-empty-state pa-empty-state--compact">
			<i class="fa fa-history" aria-hidden="true"></i>
			<div class="pa-empty-title">${esc(__('No activity yet'))}</div>
			<div class="pa-empty-subtitle">${esc(__('Tool calls will appear here.'))}</div>
		</div>`;
}

function failureHtml() {
	return `<div style="padding: 20px; text-align: center; color: var(--red-500);">${esc(__('Failed to load activity'))}</div>`;
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
