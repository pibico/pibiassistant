import { qs, on, setText } from '../dom.js';

export function mountMcpCard(root, ctx) {
	const urlEl = qs('#pa-mcp-endpoint', root);
	const offs = [];

	offs.push(ctx.bus.on('server:status', (p) => {
		if (!urlEl || !p) return;
		setText(urlEl, p.error ? __('Error loading endpoint') : p.endpointUrl);
	}));

	const copyBtn = qs('#copy-endpoint', root);
	if (copyBtn) {
		offs.push(on(copyBtn, 'click', () => {
			const url = (urlEl?.textContent || '').trim();
			if (!url || url === __('Loading...')) return;
			frappe.utils.copy_to_clipboard(url);
		}));
	}

	const settingsBtn = qs('#open-settings', root);
	if (settingsBtn) {
		offs.push(on(settingsBtn, 'click', () => frappe.set_route('Form', 'PA Core Settings')));
	}

	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
