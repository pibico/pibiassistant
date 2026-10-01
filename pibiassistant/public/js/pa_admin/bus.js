import { log } from './api.js';

const topics = new Map();

export function on(topic, fn) {
    if (!topics.has(topic)) topics.set(topic, new Set());
    topics.get(topic).add(fn);
    return () => topics.get(topic)?.delete(fn);
}

export function emit(topic, payload) {
    const handlers = topics.get(topic);
    if (!handlers) return;
    for (const fn of Array.from(handlers)) {
        try {
            const res = fn(payload);
            if (res && typeof res.catch === 'function') res.catch((e) => log.error('bus handler failed:', topic, e));
        } catch (e) {
            log.error('bus handler failed:', topic, e);
        }
    }
}

export function clearBus() {
    topics.clear();
}
