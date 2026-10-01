export function qs(sel, root = document) {
    return root ? root.querySelector(sel) : null;
}

export function qsa(sel, root = document) {
    return root ? Array.from(root.querySelectorAll(sel)) : [];
}

function applyAttr(el, key, value) {
    if (value === null || value === undefined || value === false) return;
    if (key === 'class' || key === 'className') {
        el.className = value;
    } else if (key === 'style') {
        if (typeof value === 'string') el.setAttribute('style', value);
        else Object.assign(el.style, value);
    } else if (key === 'dataset') {
        Object.entries(value).forEach(([k, v]) => {
            if (v !== null && v !== undefined) el.dataset[k] = v;
        });
    } else if (key === 'aria') {
        Object.entries(value).forEach(([k, v]) => {
            if (v !== null && v !== undefined) el.setAttribute('aria-' + k, v);
        });
    } else if (key === 'on') {
        Object.entries(value).forEach(([type, fn]) => el.addEventListener(type, fn));
    } else if (key === 'disabled' || key === 'checked' || key === 'hidden') {
        if (value) el[key] = true;
    } else {
        el.setAttribute(key, value === true ? '' : value);
    }
}

function appendKids(el, kids) {
    for (const kid of kids) {
        if (kid === null || kid === undefined || kid === false) continue;
        if (Array.isArray(kid)) appendKids(el, kid);
        else if (kid instanceof Node) el.appendChild(kid);
        else el.appendChild(document.createTextNode(String(kid)));
    }
}

export function h(tag, attrs = null, ...kids) {
    const el = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => applyAttr(el, k, v));
    appendKids(el, kids);
    return el;
}

export function setHtml(el, html) {
    if (el) el.innerHTML = html;
    return el;
}

export function setText(el, text) {
    if (el) el.textContent = text === null || text === undefined ? '' : text;
    return el;
}

export function empty(el) {
    if (el) el.replaceChildren();
    return el;
}

export function on(el, type, fn, opts) {
    if (!el) return () => {};
    el.addEventListener(type, fn, opts);
    return () => el.removeEventListener(type, fn, opts);
}

export function delegate(root, type, selector, fn, opts) {
    if (!root) return () => {};
    const capture = type === 'focus' || type === 'blur';
    const options = typeof opts === 'object' && opts ? { ...opts, capture: opts.capture || capture } : { capture };
    const handler = (event) => {
        const target = event.target instanceof Element ? event.target : null;
        const match = target ? target.closest(selector) : null;
        if (match && root.contains(match)) fn(event, match);
    };
    root.addEventListener(type, handler, options);
    return () => root.removeEventListener(type, handler, options);
}

export function escapeHtml(s) {
    return frappe.utils.escape_html(String(s ?? ''));
}

export function show(el, display = '') {
    if (el) el.style.display = display;
}

export function hide(el) {
    if (el) el.style.display = 'none';
}

export function toggleClass(el, cls, force) {
    if (el) el.classList.toggle(cls, force);
}

export function addClass(el, ...cls) {
    if (el) el.classList.add(...cls);
}

export function removeClass(el, ...cls) {
    if (el) el.classList.remove(...cls);
}

export function hasClass(el, cls) {
    return !!el && el.classList.contains(cls);
}

export function setAttrs(el, obj) {
    if (!el) return;
    Object.entries(obj).forEach(([k, v]) => {
        if (v === null || v === undefined || v === false) el.removeAttribute(k);
        else el.setAttribute(k, v === true ? '' : v);
    });
}

export function toEl(x) {
    if (x instanceof Element) return x;
    return x?.[0] ?? x?.get?.(0) ?? null;
}

export function debounce(fn, ms) {
    return frappe.utils.debounce(fn, ms);
}
