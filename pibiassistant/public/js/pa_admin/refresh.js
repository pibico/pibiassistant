import { qs, setText, on } from './dom.js';
import { state, hasToggleInProgress } from './state.js';
import { emit } from './bus.js';

let labelRoot = null;

export function updateLastRefreshedLabel() {
    const ts = state.lastRefreshedAt;
    if (!ts || !labelRoot) return;
    const seconds = Math.max(0, Math.round((Date.now() - ts.getTime()) / 1000));
    let label;
    if (seconds < 5) label = __('Updated just now');
    else if (seconds < 60) label = __('Updated {0}s ago', [seconds]);
    else label = __('Updated {0}m ago', [Math.round(seconds / 60)]);
    setText(qs('#pa-last-refreshed', labelRoot), label);
}

export function refreshAll() {
    state.lastRefreshedAt = new Date();
    updateLastRefreshedLabel();
    emit('refresh', { scope: 'all' });
}

export function startRefresh(ctx) {
    labelRoot = ctx.root;
    ctx.scope.add(() => {
        labelRoot = null;
    });
    ctx.scope.add(on(qs('#refresh-all', ctx.root), 'click', refreshAll));
    ctx.scope.interval(updateLastRefreshedLabel, 5000);
    const autoRefresh = () => {
        if (!state.autoRefreshEnabled || hasToggleInProgress()) return;
        state.lastRefreshedAt = new Date();
        updateLastRefreshedLabel();
        emit('refresh', { scope: 'auto' });
    };
    ctx.scope.interval(() => {
        if (!document.hidden) autoRefresh();
    }, 30000);
    ctx.scope.on(document, 'visibilitychange', () => {
        if (document.hidden) return;
        const ts = state.lastRefreshedAt;
        if (!ts || Date.now() - ts.getTime() >= 30000) autoRefresh();
    });
    updateLastRefreshedLabel();
}
