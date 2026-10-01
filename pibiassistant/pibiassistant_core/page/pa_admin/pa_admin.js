frappe.pages['pa-admin'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('AIDA Admin'),
        single_column: true,
    });

    frappe.require('/assets/pibiassistant/css/pa_admin.css');

    const V = '202610012';
    const entry = '/assets/pibiassistant/js/pa_admin/main.js?v=' + V;
    const host = () => page.main.get(0);
    let mod = null;
    let unmountFn = null;
    let mounting = null;

    async function ensure() {
        if (mounting) return mounting;
        mounting = (async () => {
            try {
                mod = mod || (await import(entry));
                if (unmountFn) {
                    mod.refreshAll();
                } else {
                    unmountFn = await mod.mount(host(), page);
                    if (frappe.get_route()[0] !== 'pa-admin') {
                        unmountFn();
                        unmountFn = null;
                    }
                }
            } catch (e) {
                (window.PAOLogger?.error ?? console.error)('PA Admin failed to load:', e);
                host().textContent = __('Failed to load AIDA Admin');
            } finally {
                mounting = null;
            }
        })();
        return mounting;
    }

    frappe.pages['pa-admin'].on_page_show = function () {
        ensure();
    };

    if (frappe.router && typeof frappe.router.on === 'function') {
        frappe.router.on('change', function () {
            if (frappe.get_route()[0] !== 'pa-admin' && unmountFn) {
                unmountFn();
                unmountFn = null;
            }
        });
    }
};
