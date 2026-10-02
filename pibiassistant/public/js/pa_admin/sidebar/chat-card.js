import { qs, on, setHtml, toggleClass, hasClass, hide } from '../dom.js';
import { call, log } from '../api.js';
import { state } from '../state.js';

export function renderChatStatus(root, isEnabled) {
	const pill = qs('#pa-chat-status-pill', root);
	const btn = qs('#toggle-pa-chat', root);
	const btnText = qs('#toggle-pa-chat-text', root);
	toggleClass(pill, 'pa-status-pill--running', !!isEnabled);
	toggleClass(pill, 'pa-status-pill--stopped', !isEnabled);
	toggleClass(btn, 'btn-danger', !!isEnabled);
	toggleClass(btn, 'btn-primary', !isEnabled);
	const dot = '<span class="pa-status-dot" aria-hidden="true"></span> ';
	if (isEnabled) {
		setHtml(pill, dot + __('Enabled'));
		setHtml(btnText, '<i class="ph ph-power" aria-hidden="true"></i> ' + __('Disable Chat'));
	} else {
		setHtml(pill, dot + __('Disabled'));
		setHtml(btnText, '<i class="ph ph-play" aria-hidden="true"></i> ' + __('Enable Chat'));
	}
}

function publish(ctx, enabled, userToggled) {
	state.chatEnabled = !!enabled;
	renderChatStatus(ctx.root, enabled);
	ctx.bus.emit('chat:status', { enabled: !!enabled, userToggled });
}

export async function loadChatStatus(ctx) {
	let msg;
	try {
		msg = await call('pibiassistant.pibiassistant_chat.api.get_chat_status', {}, { type: 'GET', silent: true });
	} catch (err) {
		log.warn('get_chat_status', err);
		if (ctx.scope.alive) hide(qs('#pa-chat-card', ctx.root));
		return;
	}
	if (!ctx.scope.alive) return;
	if (!msg) {
		hide(qs('#pa-chat-card', ctx.root));
		return;
	}
	publish(ctx, msg.enabled, false);
}

async function doToggle(ctx, newState) {
	const btn = qs('#toggle-pa-chat', ctx.root);
	if (btn) btn.disabled = true;
	let data;
	try {
		data = await call('pibiassistant.pibiassistant_chat.api.toggle_chat', { enabled: newState }, { type: 'POST', silent: true });
	} catch (err) {
		log.error('toggle_chat', err);
		if (ctx.scope.alive) {
			if (btn) btn.disabled = false;
			ctx.toast.error(__('Error toggling chat'));
		}
		return;
	}
	if (!ctx.scope.alive) return;
	if (btn) btn.disabled = false;
	if (!data) {
		ctx.toast.error(__('Error toggling chat'));
		return;
	}
	if (data.enabled) {
		if (typeof window.paoWidgetRemount === 'function') window.paoWidgetRemount();
		ctx.toast.alert(__('AIDA Chat enabled.'), 'green');
	} else {
		if (typeof window.paoWidgetTeardown === 'function') window.paoWidgetTeardown();
		ctx.toast.alert(__('AIDA Chat disabled.'), 'orange');
	}
	publish(ctx, data.enabled, true);
}

export function toggleChat(ctx) {
	const isEnabled = hasClass(qs('#pa-chat-status-pill', ctx.root), 'pa-status-pill--running');
	const newState = isEnabled ? 0 : 1;
	if (newState === 0) {
		ctx.toast.confirm(
			__('Disable AIDA Chat? The in-Frappe chat widget and /aida SPA will become unavailable to users.'),
			() => doToggle(ctx, newState),
			null,
			{ title: __('Disable AIDA Chat'), confirmLabel: __('Disable') }
		);
	} else {
		doToggle(ctx, newState);
	}
}

export function mountChatCard(root, ctx) {
	const offs = [];
	const btn = qs('#toggle-pa-chat', root);
	if (btn) offs.push(on(btn, 'click', () => toggleChat(ctx)));
	offs.push(ctx.bus.on('refresh', (p) => {
		if (p?.scope === 'initial' || p?.scope === 'all') loadChatStatus(ctx);
	}));
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
