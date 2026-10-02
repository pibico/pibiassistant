import * as toast from './toast.js';

export const log = {
    debug: (...a) => console.debug(...a),
    warn: (...a) => (window.PAOLogger?.warn ?? console.warn)(...a),
    error: (...a) => (window.PAOLogger?.error ?? console.error)(...a),
};

const DEFAULT_TIMEOUT_MS = 20000;

export function call(method, args = {}, { type = 'POST', freeze = false, silent = false, errorMessage, timeout = DEFAULT_TIMEOUT_MS } = {}) {
    return new Promise((resolve, reject) => {
        let settled = false;
        let timer = null;
        const finish = (fn, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            fn(value);
        };
        // frappe.call never invokes error for non-JSON bodies or hung requests, so settle ourselves.
        const fail = (response) => {
            if (settled) return;
            log.error(method, response);
            if (!silent) toast.error(errorMessage || __('Request failed'));
            const err = new Error('Request failed: ' + method);
            err.method = method;
            err.response = response;
            finish(reject, err);
        };
        timer = setTimeout(() => fail({ timeout: true }), timeout);
        try {
            frappe.call({
                method,
                args,
                type,
                freeze,
                silent: true,
                callback: (response) => finish(resolve, response ? response.message : undefined),
                error: fail,
            });
        } catch (e) {
            fail(e);
        }
    });
}

export function callOrNull(method, args, opts) {
    return call(method, args, { silent: true, ...opts }).catch(() => null);
}

export function guard(ctx, fn) {
    return (...a) => (ctx.scope.alive ? fn(...a) : undefined);
}
