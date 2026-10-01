import { qs, setText } from '../dom.js';
import { callOrNull } from '../api.js';
import { state } from '../state.js';

function setCount(ctx, key, value) {
	if (!ctx.scope.alive) return;
	state.counts[key] = value;
	setText(qs(`#tab-count-${key}`, ctx.root), value);
}

export async function loadToolCount(ctx) {
	const stats = await callOrNull('pibiassistant.api.admin_api.get_tool_stats', {}, { silent: true });
	if (stats) setCount(ctx, 'tools', stats.total_tools || 0);
}

async function loadListCount(ctx, method, key) {
	const msg = await callOrNull(method, {}, { silent: true });
	if (msg && msg.success) setCount(ctx, key, msg.total || 0);
}

export function loadStats(ctx) {
	return Promise.all([
		loadToolCount(ctx),
		loadListCount(ctx, 'pibiassistant.api.admin_api.get_prompt_templates_list', 'prompts'),
		loadListCount(ctx, 'pibiassistant.api.admin_api.get_skills_list', 'skills'),
	]);
}

export function mountCounts(root, ctx) {
	const offs = [
		ctx.bus.on('refresh', (p) => {
			if (p?.scope) loadStats(ctx);
		}),
		ctx.bus.on('tools:changed', () => loadToolCount(ctx)),
		ctx.bus.on('prompts:loaded', (p) => setCount(ctx, 'prompts', p?.count ?? 0)),
		ctx.bus.on('skills:loaded', (p) => setCount(ctx, 'skills', p?.count ?? 0)),
	];
	return function unmount() {
		offs.splice(0).forEach((fn) => fn());
	};
}
