import { qs, qsa, h, on, empty, setText, hide, toggleClass } from '../dom.js';
import { call, log } from '../api.js';

function renderServices(list, services) {
	empty(list);
	Object.keys(services || {}).forEach((name) => {
		const s = services[name];
		list.appendChild(h('li', { class: 'pa-svc', dataset: { svc: `${name} API` } },
			h('span', { class: s.configured ? 'pa-status-pill' : 'pa-status-pill pa-status-pill--stopped' },
				h('span', { class: 'pa-status-dot', aria: { hidden: 'true' } }),
				` ${name}`),
			h('span', { class: 'pa-sidebar-subtle svc-detail' }, s.configured ? s.url : __('Not configured'))));
	});
}

function applyTestResults(list, res) {
	let failed = 0;
	qsa('li', list).forEach((li) => {
		const st = res[li.dataset.svc];
		if (!st) return;
		const pill = qs('.pa-status-pill', li);
		toggleClass(pill, 'pa-status-pill--running', !!st.ok);
		toggleClass(pill, 'pa-status-pill--stopped', !st.ok);
		if (!st.ok) {
			failed++;
			setText(qs('.svc-detail', li), st.error || __('No response'));
		}
	});
	return failed;
}

export async function loadAidaServices(ctx, showToast) {
	const root = ctx.root;
	const list = qs('#pa-aida-services', root);
	let o;
	try {
		o = (await call('pibiassistant.pibiassistant_chat.api.aida.get_overview', {}, { silent: true })) || {};
	} catch (err) {
		log.error('get_overview', err);
		if (ctx.scope.alive) hide(qs('#pa-aida-card', root));
		return;
	}
	if (!ctx.scope.alive) return;
	const model = [o.provider, o.model].filter(Boolean).join(' / ');
	setText(qs('#pa-aida-model', root), model ? __('Model: {0}', [model]) : __('No default model'));
	setText(qs('#analytics-model', root), o.model || '—');
	renderServices(list, o.services);

	let res;
	try {
		res = (await call('pibiassistant.pibiassistant_chat.api.aida.test_connections', {}, { silent: true })) || {};
	} catch (err) {
		log.error('test_connections', err);
		return;
	}
	if (!ctx.scope.alive) return;
	const failed = applyTestResults(list, res);
	if (showToast) {
		ctx.toast.alert(
			failed ? __('{0} AIDA service(s) with problems', [failed]) : __('AIDA services operational'),
			failed ? 'orange' : 'green'
		);
	}
}

export function mountAidaCard(root, ctx) {
	const offs = [];
	const test = qs('#test-aida', root);
	if (test) offs.push(on(test, 'click', () => loadAidaServices(ctx, true)));
	const cfg = qs('#configure-aida', root);
	if (cfg) offs.push(on(cfg, 'click', () => frappe.set_route('Form', 'PA Core Settings')));
	offs.push(ctx.bus.on('refresh', (p) => {
		if (p?.scope === 'initial' || p?.scope === 'all') loadAidaServices(ctx, false);
	}));
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
