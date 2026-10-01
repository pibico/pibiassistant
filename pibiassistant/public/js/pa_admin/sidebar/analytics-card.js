import { qs, setText, setHtml, empty, show, hide } from '../dom.js';
import { call, log } from '../api.js';
import { fmtNumber } from '../utils.js';

export function renderSparkline(host, series) {
	if (!host || !series || series.length === 0) {
		empty(host);
		return;
	}
	const counts = series.map((d) => d.count || 0);
	const max = Math.max(...counts);
	const width = 100;
	const height = 24;
	const pad = 2;
	const innerW = width - pad * 2;
	const innerH = height - pad * 2;
	const stepX = counts.length > 1 ? innerW / (counts.length - 1) : 0;
	const points = counts.map((c, i) => {
		const x = (pad + i * stepX).toFixed(2);
		const y = max > 0 ? (pad + (1 - c / max) * innerH).toFixed(2) : pad + innerH;
		return `${x},${y}`;
	}).join(' ');
	const last = series[series.length - 1];
	const tip = last ? `${last.count} on ${last.day}` : '';
	setHtml(host, `
		<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"
			 class="pa-spark-svg" role="img" aria-label="${frappe.utils.escape_html(tip)}">
			<polyline points="${points}" />
		</svg>
	`);
}

export async function loadChatAnalytics(ctx) {
	const card = qs('#pa-chat-analytics-card', ctx.root);
	let msg;
	try {
		msg = await call('pibiassistant.pibiassistant_chat.api.get_chat_analytics', {}, { type: 'GET', silent: true });
	} catch (err) {
		log.warn('get_chat_analytics', err);
		if (ctx.scope.alive) hide(card);
		return;
	}
	if (!ctx.scope.alive) return;
	const data = msg || {};
	if (!data.enabled) {
		hide(card);
		return;
	}
	show(card);
	setText(qs('#analytics-monthly', ctx.root), fmtNumber(data.monthly_messages));
	setText(qs('#analytics-total', ctx.root), fmtNumber(data.total_messages));
	setText(qs('#analytics-users', ctx.root), fmtNumber(data.active_users));
	renderSparkline(qs('#analytics-spark', ctx.root), data.series || []);
}

export function mountAnalyticsCard(root, ctx) {
	const offs = [];
	offs.push(ctx.bus.on('refresh', (p) => {
		if (p?.scope) loadChatAnalytics(ctx);
	}));
	offs.push(ctx.bus.on('chat:status', (p) => {
		if (p?.userToggled) loadChatAnalytics(ctx);
	}));
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
