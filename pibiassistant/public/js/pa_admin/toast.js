const esc = (s) => frappe.utils.escape_html(String(s ?? ''));

export function alert(msg, indicator = 'green', seconds = 5, { html = false } = {}) {
    frappe.show_alert({ message: html ? msg : esc(msg), indicator }, seconds);
}

export function success(msg) {
    alert(msg, 'green');
}

export function warning(msg) {
    alert(msg, 'orange');
}

export function error(msg) {
    alert(msg, 'red');
}

export function info(msg, seconds = 5) {
    alert(msg, 'blue', seconds);
}

export function msgprint(opts) {
    return frappe.msgprint(opts);
}

export function confirm(message, onYes, onNo) {
    return frappe.confirm(esc(message), onYes, onNo);
}
