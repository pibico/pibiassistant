import { renderMarkdown } from '../utils.js';

const BLOCKED = 'script,style,iframe,object,embed,link,meta,base,form,svg,math,template,noscript';
const URL_ATTRS = ['href', 'src', 'xlink:href', 'action', 'formaction', 'srcset', 'poster'];
const SAFE_URL = /^\s*(https?:|mailto:|tel:|#|\/|\.\/|\.\.\/)/i;

export function sanitizeHtml(html) {
	const doc = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html');
	doc.body.querySelectorAll(BLOCKED).forEach((el) => el.remove());
	doc.body.querySelectorAll('*').forEach((el) => {
		for (const attr of Array.from(el.attributes)) {
			const name = attr.name.toLowerCase();
			if (name.startsWith('on') || name === 'style') {
				el.removeAttribute(attr.name);
			} else if (URL_ATTRS.includes(name)) {
				const compact = attr.value.replace(/[\u0000- ]/g, '');
				if (!SAFE_URL.test(compact) && /^[a-z][a-z0-9+.-]*:/i.test(compact)) el.removeAttribute(attr.name);
			}
		}
		if (el.tagName === 'A' && el.getAttribute('target') === '_blank') el.setAttribute('rel', 'noopener noreferrer');
	});
	return doc.body.innerHTML;
}

export function renderSafeMarkdown(text) {
	return sanitizeHtml(renderMarkdown(text));
}
