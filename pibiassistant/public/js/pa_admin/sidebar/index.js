import { mountMcpCard } from './mcp-card.js';
import { mountAidaCard } from './aida-card.js';
import { mountChatCard } from './chat-card.js';
import { mountAnalyticsCard } from './analytics-card.js';
import { mountQuickActions } from './quick-actions.js';
import { mountActivityCard } from './activity-card.js';
import { log } from '../api.js';

export function mountSidebar(root, ctx) {
	const unmounts = [];
	const cards = [mountMcpCard, mountAidaCard, mountChatCard, mountAnalyticsCard, mountQuickActions, mountActivityCard];
	for (const mount of cards) {
		try {
			unmounts.push(mount(root, ctx));
		} catch (err) {
			log.error('pa_admin sidebar mount failed', err);
		}
	}
	return function unmount() {
		unmounts.splice(0).reverse().forEach((fn) => {
			try { fn?.(); } catch (err) { log.error('pa_admin sidebar unmount failed', err); }
		});
	};
}
