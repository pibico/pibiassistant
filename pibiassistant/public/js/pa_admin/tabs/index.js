import { qs, qsa, delegate, addClass, removeClass } from '../dom.js';
import { state } from '../state.js';
import { bindTablist } from '../registry/tablist.js';
import { log } from '../api.js';
import { mountCounts } from './counts.js';
import { mountPrompts, loadPromptTemplatesView } from './prompts.js';
import { mountSkills, loadSkillsView } from './skills.js';

function setActive(root, name) {
	qsa('.pa-top-tab', root).forEach((tab) => {
		const active = tab.dataset.tab === name;
		if (active) addClass(tab, 'active'); else removeClass(tab, 'active');
		tab.setAttribute('aria-selected', active ? 'true' : 'false');
		tab.setAttribute('tabindex', active ? '0' : '-1');
	});
	qsa('.pa-tab-panel', root).forEach((p) => removeClass(p, 'active'));
	addClass(qs(`#tab-panel-${name}`, root), 'active');
}

export function switchTab(ctx, name) {
	if (state.activeTab === name) return;
	state.activeTab = name;
	setActive(ctx.root, name);
	if (name === 'prompts' && state.promptsData.length === 0) loadPromptTemplatesView(ctx);
	if (name === 'skills' && state.skillsData.length === 0) loadSkillsView(ctx);
	ctx.bus.emit('tab:changed', { tab: name });
}

export function mountTopTabs(root, ctx) {
	const offs = [];
	const subs = [mountCounts, mountPrompts, mountSkills];
	subs.forEach((mount) => {
		try {
			offs.push(mount(root, ctx));
		} catch (err) {
			log.error('pa_admin tabs mount failed', err);
		}
	});

	const tablist = qs('.pa-top-tabs', root);
	if (tablist) {
		offs.push(delegate(tablist, 'click', '.pa-top-tab', (e, tab) => switchTab(ctx, tab.dataset.tab)));
		offs.push(bindTablist(tablist, {
			tabSelector: '.pa-top-tab',
			onActivate: (tab) => switchTab(ctx, tab.dataset.tab),
		}));
	}
	return function unmount() {
		offs.splice(0).reverse().forEach((fn) => {
			try { fn?.(); } catch (err) { log.error('pa_admin tabs unmount failed', err); }
		});
	};
}
