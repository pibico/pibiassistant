import { escapeHtml } from './dom.js';

let converter = null;

export function renderMarkdown(text) {
    if (!text) return '';
    if (!converter) {
        if (!frappe.md2html) frappe.markdown('');
        if (frappe.md2html) {
            const Showdown = frappe.md2html.constructor;
            converter = new Showdown({
                tables: true,
                ghCodeBlocks: true,
                strikethrough: true,
                tasklists: true,
                encodeEmails: true,
                ellipsis: true,
            });
        }
    }
    if (converter) return converter.makeHtml(text);
    return `<pre>${escapeHtml(text)}</pre>`;
}

export function highlight(text, query) {
    const raw = text || '';
    const esc = escapeHtml;
    const needle = String(query || '').trim();
    if (!needle) return esc(raw);
    const re = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    let out = '';
    let last = 0;
    let m;
    while ((m = re.exec(raw))) {
        out += esc(raw.slice(last, m.index)) + '<mark class="pa-hl">' + esc(m[0]) + '</mark>';
        last = m.index + m[0].length;
    }
    return out + esc(raw.slice(last));
}

export function skeletonCards(rows) {
    const n = rows || 4;
    let out = '<div class="pa-skeleton-wrap">';
    for (let i = 0; i < n; i++) {
        out += `
                <div class="pa-skeleton-card">
                    <div class="pa-skeleton-line pa-skeleton-line--title"></div>
                    <div class="pa-skeleton-line pa-skeleton-line--body"></div>
                    <div class="pa-skeleton-line pa-skeleton-line--body short"></div>
                </div>
            `;
    }
    return out + '</div>';
}

export function fmtNumber(n) {
    const x = Number(n || 0);
    if (x >= 1000000) return (x / 1000000).toFixed(1) + 'M';
    if (x >= 1000) return (x / 1000).toFixed(1) + 'K';
    return String(Math.round(x));
}
