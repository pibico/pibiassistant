import { on as domOn, delegate as domDelegate } from './dom.js';

export function createScope() {
    const cleanups = [];
    const scope = {
        alive: true,
        on(el, type, fn, opts) {
            scope.add(domOn(el, type, fn, opts));
        },
        delegate(root, type, selector, fn, opts) {
            scope.add(domDelegate(root, type, selector, fn, opts));
        },
        interval(fn, ms) {
            const id = setInterval(fn, ms);
            scope.add(() => clearInterval(id));
            return id;
        },
        timeout(fn, ms) {
            const id = setTimeout(fn, ms);
            scope.add(() => clearTimeout(id));
            return id;
        },
        add(cleanupFn) {
            if (typeof cleanupFn === 'function') cleanups.push(cleanupFn);
        },
        dispose() {
            if (!scope.alive) return;
            scope.alive = false;
            while (cleanups.length) {
                try {
                    cleanups.pop()();
                } catch (e) {
                    console.error(e);
                }
            }
        },
    };
    return scope;
}
