// After editing any module, hard-reload: only this entry carries the ?v= cache buster.
import { toEl } from './dom.js';
import { state, resetState } from './state.js';
import { emit, on as busOn, clearBus } from './bus.js';
import { call, log, guard } from './api.js';
import * as toast from './toast.js';
import * as utils from './utils.js';
import { createScope } from './lifecycle.js';
import { renderLayout } from './layout.js';
import { mountHeader } from './header.js';
import { startRefresh, refreshAll as refreshAllNow } from './refresh.js';
import { mountTopTabs } from './tabs/index.js';
import { mountRegistry } from './registry/index.js';
import { mountSidebar } from './sidebar/index.js';

const BUILD = new URL(import.meta.url).searchParams.get('v');

let current = null;

export function unmount() {
    if (!current) return;
    const { scope, unmounts } = current;
    current = null;
    for (const fn of unmounts.reverse()) {
        try {
            fn();
        } catch (e) {
            log.error('unmount failed:', e);
        }
    }
    scope.dispose();
    clearBus();
}

export function refreshAll() {
    if (current) refreshAllNow();
}

export async function mount(wrapperEl, page) {
    const host = toEl(wrapperEl);
    if (current && current.host === host) return unmount;
    unmount();

    resetState();
    const scope = createScope();
    const root = renderLayout(host);
    const ctx = {
        page,
        root,
        scope,
        state,
        bus: { on: busOn, emit },
        api: { call, guard },
        toast,
        utils,
        build: BUILD,
    };
    const unmounts = [];
    current = { host, scope, unmounts };

    const features = [
        ['header', mountHeader],
        ['tabs', mountTopTabs],
        ['registry', mountRegistry],
        ['sidebar', mountSidebar],
    ];
    for (const [name, mountFeature] of features) {
        try {
            const un = mountFeature(root, ctx);
            if (typeof un === 'function') unmounts.push(un);
        } catch (e) {
            log.error('Failed to mount ' + name + ':', e);
        }
    }

    state.lastRefreshedAt = new Date();
    startRefresh(ctx);
    emit('refresh', { scope: 'initial' });
    return unmount;
}
