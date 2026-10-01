import { qs, setHtml, setText, on, addClass, removeClass } from './dom.js';
import { call, log } from './api.js';
import { emit, on as busOn } from './bus.js';
import * as toast from './toast.js';

const FALLBACK_PATH = '/api/method/pibiassistant.api.pa_endpoint.handle_mcp';

let unavailable = false;

function renderServerStatus(root, isEnabled) {
    unavailable = false;
    const icon = qs('#server-status-icon', root);
    const pill = qs('#server-status-pill', root);
    const btn = qs('#toggle-server', root);
    const btnText = qs('#toggle-server-text', root);
    setText(qs('#server-status-text', root), 'AIDA');
    if (isEnabled) {
        removeClass(icon, 'inactive');
        addClass(icon, 'active');
        removeClass(pill, 'pa-status-pill--stopped');
        addClass(pill, 'pa-status-pill--running');
        setHtml(pill, '<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Running'));
        removeClass(btn, 'btn-primary');
        addClass(btn, 'btn-danger');
        setHtml(btnText, '<i class="ph ph-stop" aria-hidden="true"></i> ' + __('Disable'));
    } else {
        removeClass(icon, 'active');
        addClass(icon, 'inactive');
        removeClass(pill, 'pa-status-pill--running');
        addClass(pill, 'pa-status-pill--stopped');
        setHtml(pill, '<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Stopped'));
        removeClass(btn, 'btn-danger');
        addClass(btn, 'btn-primary');
        setHtml(btnText, '<i class="ph ph-play" aria-hidden="true"></i> ' + __('Enable'));
    }
}

function renderUnavailable(root) {
    unavailable = true;
    const icon = qs('#server-status-icon', root);
    const pill = qs('#server-status-pill', root);
    const btn = qs('#toggle-server', root);
    setText(qs('#server-status-text', root), 'AIDA');
    removeClass(icon, 'active');
    addClass(icon, 'inactive');
    removeClass(pill, 'pa-status-pill--running');
    addClass(pill, 'pa-status-pill--stopped');
    setHtml(pill, '<span class="pa-status-dot" aria-hidden="true"></span> ' + __('Unavailable'));
    removeClass(btn, 'btn-danger');
    addClass(btn, 'btn-primary');
    setHtml(qs('#toggle-server-text', root), '<i class="ph ph-arrows-clockwise" aria-hidden="true"></i> ' + __('Retry'));
    if (btn) btn.disabled = false;
}

async function loadServerStatus(ctx) {
    try {
        const settings = await call(
            'frappe.client.get',
            { doctype: 'PA Core Settings', name: 'PA Core Settings' },
            { silent: true }
        );
        if (!ctx.scope.alive) return;
        if (!settings) throw new Error('empty settings');
        renderServerStatus(ctx.root, settings.server_enabled);
        const endpointUrl = settings.mcp_endpoint_url || window.location.origin + FALLBACK_PATH;
        emit('server:status', { enabled: !!settings.server_enabled, endpointUrl });
    } catch (e) {
        log.error('Failed to load server status:', e.response);
        if (!ctx.scope.alive) return;
        renderUnavailable(ctx.root);
        toast.error(__('Failed to load server status'));
        emit('server:status', { error: true });
    }
}

async function toggleServer(ctx) {
    let settings;
    try {
        settings = await call('pibiassistant.api.admin_api.get_server_settings', {}, { silent: true });
    } catch (e) {
        if (ctx.scope.alive) toast.error(__('Error updating server settings'));
        return;
    }
    if (!ctx.scope.alive) return;
    if (!settings) {
        loadServerStatus(ctx);
        return;
    }
    const newState = settings.server_enabled ? 0 : 1;

    const doToggle = async () => {
        try {
            const result = await call(
                'pibiassistant.api.admin_api.update_server_settings',
                { server_enabled: newState },
                { silent: true }
            );
            if (!ctx.scope.alive) return;
            if (!result || result.success === false) {
                toast.error(result?.message || __('Error updating server settings'));
                return;
            }
            toast.alert(
                newState ? __('AIDA Server Enabled') : __('AIDA Server Disabled'),
                newState ? 'green' : 'orange'
            );
            emit('server:toggled', { enabled: !!newState });
            ctx.scope.timeout(() => loadServerStatus(ctx), 300);
        } catch (e) {
            if (ctx.scope.alive) toast.error(__('Error updating server settings'));
        }
    };

    if (newState === 0) {
        toast.confirm(
            __('Disable the AIDA server? All MCP clients will lose access until it is re-enabled.'),
            doToggle
        );
    } else {
        doToggle();
    }
}

export function mountHeader(root, ctx) {
    unavailable = false;
    ctx.scope.add(on(qs('#toggle-server', root), 'click', () => (unavailable ? loadServerStatus(ctx) : toggleServer(ctx))));
    ctx.scope.add(
        busOn('refresh', () => {
            loadServerStatus(ctx);
        })
    );
    return () => {};
}
