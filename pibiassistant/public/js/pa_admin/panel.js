const stack = [];
let seq = 0;
let prevOverflow = null;
let keyBound = false;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const esc = (s) => frappe.utils.escape_html(String(s ?? ''));
const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function focusables(panel) {
    return Array.from(panel.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

function onKeydown(e) {
    const top = stack[stack.length - 1];
    if (!top) return;
    if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        top.close('escape');
    } else if (e.key === 'Tab') {
        const items = focusables(top.el);
        if (!items.length) {
            e.preventDefault();
            top.el.focus();
            return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (!top.el.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
        } else if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }
}

function bindKeys() {
    if (keyBound) return;
    document.addEventListener('keydown', onKeydown, true);
    keyBound = true;
    prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
}

function unbindKeys() {
    if (!keyBound || stack.length) return;
    document.removeEventListener('keydown', onKeydown, true);
    keyBound = false;
    document.body.style.overflow = prevOverflow || '';
    prevOverflow = null;
}

function resolveFocus(target) {
    const el = typeof target === 'function' ? target() : target;
    return el && el.isConnected && typeof el.focus === 'function' ? el : null;
}

/**
 * Right-edge slide panel (pibiCo guideline: no centered modals).
 * Mounted inside the .pa-admin-container so every rule stays scoped to the page.
 * `body` / `footer` accept an HTML string or a Node. Resolves focus back to
 * `returnFocus` (element or getter) or to the element focused when it opened.
 */
export function openPanel({ title = '', body = '', footer = null, root = null, returnFocus = null, onClose = null, className = '' } = {}) {
    const host = root || document.querySelector('.pa-admin-container') || document.body;
    const opener = document.activeElement;
    const id = `pa-panel-title-${++seq}`;
    const layer = document.createElement('div');
    layer.className = 'pa-panel-layer';
    layer.style.zIndex = String(10060 + stack.length * 2);
    layer.innerHTML = `
        <div class="pa-panel-backdrop"></div>
        <aside class="pa-panel ${esc(className)}" role="dialog" aria-modal="true" aria-labelledby="${id}" tabindex="-1">
            <header class="pa-panel-header">
                <h2 class="pa-panel-title" id="${id}"></h2>
                <button type="button" class="pa-panel-close" aria-label="${esc(__('Close'))}"><i class="ph ph-x" aria-hidden="true"></i></button>
            </header>
            <div class="pa-panel-body"></div>
            <footer class="pa-panel-footer" hidden></footer>
        </aside>`;
    const el = layer.querySelector('.pa-panel');
    const bodyEl = layer.querySelector('.pa-panel-body');
    const footerEl = layer.querySelector('.pa-panel-footer');
    const titleEl = layer.querySelector('.pa-panel-title');
    titleEl.textContent = title;

    const fill = (target, content) => {
        if (content instanceof Node) target.replaceChildren(content);
        else target.innerHTML = content || '';
    };
    fill(bodyEl, body);
    if (footer) {
        fill(footerEl, footer);
        footerEl.hidden = false;
    }

    let closed = false;
    const api = {
        el,
        bodyEl,
        footerEl,
        setTitle(t) { titleEl.textContent = t; },
        close(reason = 'close', { immediate = false } = {}) {
            if (closed) return;
            closed = true;
            const i = stack.indexOf(api);
            if (i >= 0) stack.splice(i, 1);
            const finish = () => {
                layer.remove();
                unbindKeys();
                const back = resolveFocus(returnFocus) || resolveFocus(opener);
                if (back) back.focus();
                if (onClose) onClose(reason);
            };
            layer.classList.remove('is-open');
            if (immediate || reduceMotion()) {
                finish();
                return;
            }
            let done = false;
            const once = () => {
                if (done) return;
                done = true;
                finish();
            };
            el.addEventListener('transitionend', (ev) => { if (ev.target === el) once(); });
            setTimeout(once, 400);
        },
    };

    layer.querySelector('.pa-panel-backdrop').addEventListener('click', () => api.close('backdrop'));
    layer.querySelector('.pa-panel-close').addEventListener('click', () => api.close('close'));

    host.appendChild(layer);
    stack.push(api);
    bindKeys();
    void layer.offsetWidth;
    layer.classList.add('is-open');

    const first = focusables(bodyEl)[0] || focusables(footerEl)[0];
    (first || el).focus({ preventScroll: true });
    return api;
}

export function confirm(message, onYes, onNo, { title = __('Confirm'), confirmLabel = __('Confirm'), danger = true } = {}) {
    let answered = false;
    let body = message;
    if (!(message instanceof Node)) {
        body = document.createElement('p');
        body.className = 'pa-panel-text';
        body.textContent = message;
    }
    const footer = document.createElement('div');
    footer.className = 'pa-panel-actions';
    footer.innerHTML = `
        <button type="button" class="btn btn-default pa-panel-cancel">${esc(__('Cancel'))}</button>
        <button type="button" class="btn ${danger ? 'btn-danger' : 'btn-primary'} pa-panel-confirm">${esc(confirmLabel)}</button>`;
    const panel = openPanel({
        title,
        body,
        footer,
        onClose: () => { if (!answered && onNo) onNo(); },
    });
    footer.querySelector('.pa-panel-cancel').addEventListener('click', () => panel.close('cancel'));
    const yes = footer.querySelector('.pa-panel-confirm');
    yes.addEventListener('click', () => {
        answered = true;
        panel.close('confirm');
        if (onYes) onYes();
    });
    yes.focus({ preventScroll: true });
    return panel;
}

export function msgprint(opts) {
    const o = typeof opts === 'string' ? { message: opts } : opts || {};
    const body = document.createElement('div');
    body.className = 'pa-panel-text';
    body.innerHTML = Array.isArray(o.message) ? o.message.join('<br>') : String(o.message ?? '');
    return openPanel({ title: o.title || __('Message'), body });
}

export function closeAll() {
    for (const p of stack.slice().reverse()) p.close('unmount', { immediate: true });
}
