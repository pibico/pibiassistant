frappe.pages['pa-admin'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('AIDA Admin'),
        single_column: true,
    });

    // nginx caches /assets for a year: versioned module URLs come from the server as an import map
    const entry = '/assets/pibiassistant/js/pa_admin/main.js';
    async function installAssetVersions() {
        if (document.getElementById('pa-admin-importmap')) return;
        const versions = await frappe.xcall('pibiassistant.api.admin_api.get_import_map');
        const map = document.createElement('script');
        map.type = 'importmap';
        map.id = 'pa-admin-importmap';
        map.textContent = JSON.stringify({ imports: versions.imports });
        document.head.appendChild(map);
        // frappe.require tells CSS from JS by the file extension, so a ?v= query would run it as a script
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.id = 'pa-admin-css';
        link.href = versions.css;
        const loaded = new Promise((resolve) => {
            link.onload = link.onerror = resolve;
            setTimeout(resolve, 3000);
        });
        document.head.appendChild(link);
        await loaded;
    }
    const host = () => page.main.get(0);
    let mod = null;
    let unmountFn = null;
    let mounting = null;

    async function ensure() {
        if (mounting) return mounting;
        mounting = (async () => {
            try {
                await installAssetVersions();
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
