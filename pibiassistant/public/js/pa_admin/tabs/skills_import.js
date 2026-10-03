import { qs, on, escapeHtml as esc } from '../dom.js';
import { call, log } from '../api.js';
import { openPanel } from '../panel.js';
import * as toast from '../toast.js';

const PREVIEW = 'pibiassistant.api.admin_api.preview_skill_package';
const IMPORT = 'pibiassistant.api.admin_api.import_skill_package';
const EXPORT = 'pibiassistant.api.admin_api.export_skill_package';

function fmtSize(bytes) {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const KIND_ICON = { reference: 'ph-book-open', asset: 'ph-image', script: 'ph-terminal-window', other: 'ph-file' };

export function filesTableHtml(files) {
	if (!files || !files.length) return `<div class="pa-muted">${esc(__('No files'))}</div>`;
	const rows = files.map((f) => `
		<tr>
			<td><i class="ph ${KIND_ICON[f.kind] || 'ph-file'}" aria-hidden="true"></i> <span class="pa-file-path">${esc(f.path)}</span></td>
			<td>${esc(__(f.kind))}</td>
			<td class="pa-file-size">${esc(fmtSize(f.size || 0))}</td>
		</tr>`).join('');
	return `<table class="pa-files-table"><thead><tr><th>${esc(__('File'))}</th><th>${esc(__('Kind'))}</th><th>${esc(__('Size'))}</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function warningsHtml(warnings) {
	if (!warnings || !warnings.length) return '';
	return `<ul class="pa-import-warnings" role="list">${warnings.map((w) => `<li><i class="ph ph-warning" aria-hidden="true"></i> ${esc(w.message)}</li>`).join('')}</ul>`;
}

const ACTION_TEXT = {
	create: () => __('A new skill will be created.'),
	update: () => __('The existing skill with this name will be updated and its version raised.'),
	unchanged: () => __('This exact package is already imported: nothing would change.'),
	refused_system: () => __('This name belongs to a skill shipped with the system, which cannot be replaced.'),
};

async function upload(file) {
	const form = new FormData();
	form.append('file', file, file.name);
	form.append('is_private', '1');
	const res = await fetch('/api/method/upload_file', {
		method: 'POST',
		headers: { 'X-Frappe-CSRF-Token': window.frappe && frappe.csrf_token },
		body: form,
		credentials: 'same-origin',
	});
	if (!res.ok) throw new Error(`upload ${res.status}`);
	const body = await res.json();
	if (!body.message || !body.message.file_url) throw new Error('upload failed');
	return body.message.file_url;
}

export function openImportPanel(ctx, { onDone } = {}) {
	const panel = openPanel({
		title: __('Import .skill'),
		root: ctx.root,
		returnFocus: () => qs('#skill-import-btn', ctx.root),
		body: `
			<div class="pa-import">
				<p class="pa-muted">${esc(__('A .skill package is a zip with SKILL.md and optional references/, assets/ and scripts/ folders. Scripts and templates are stored for MCP clients to read or run on their side; this server never runs them.'))} ${esc(__('A plain SKILL.md file works too.'))}</p>
				<label class="pa-import-pick">
					<span>${esc(__('Choose a .skill, .zip or SKILL.md file'))}</span>
					<input type="file" id="pa-import-file" accept=".skill,.zip,.md,text/markdown,application/zip">
				</label>
				<div id="pa-import-result" aria-live="polite"></div>
			</div>`,
	});
	const result = qs('#pa-import-result', panel.bodyEl);
	const input = qs('#pa-import-file', panel.bodyEl);
	const offs = [];
	let fileUrl = null;

	const showError = (msg) => { result.innerHTML = `<div class="pa-error-block" role="alert">${esc(msg)}</div>`; };

	offs.push(on(input, 'change', async () => {
		const file = input.files && input.files[0];
		if (!file) return;
		result.innerHTML = `<div class="pa-muted"><i class="ph ph-spinner ph-spin" aria-hidden="true"></i> ${esc(__('Reading the package...'))}</div>`;
		let preview;
		try {
			fileUrl = await upload(file);
			preview = await call(PREVIEW, { file_url: fileUrl }, { silent: true });
		} catch (err) {
			log.error('skill preview', err);
			showError(__('The package could not be read.'));
			return;
		}
		if (!preview || !preview.success) { showError((preview && preview.error) || __('The package could not be read.')); return; }
		const canImport = preview.schema_ready && preview.action !== 'refused_system' && preview.action !== 'unchanged';
		result.innerHTML = `
			<div class="pa-import-card">
				<h3 class="pa-import-title">${esc(preview.title)} <span class="pa-meta-chip">${esc(preview.skill_id)}</span> <span class="pa-meta-chip">v${esc(preview.version)}</span></h3>
				<p>${esc(preview.description)}</p>
				<p class="pa-muted">${esc((ACTION_TEXT[preview.action] || (() => ''))())}${preview.schema_ready ? '' : ' ' + esc(__('The package schema is not installed on this site yet: run bench migrate first.'))}</p>
				${warningsHtml(preview.warnings)}
				<h4 class="pa-import-sub">${esc(__('Files'))} (${(preview.files || []).length}, ${esc(fmtSize(preview.total_size || 0))})</h4>
				${filesTableHtml(preview.files)}
			</div>
			${canImport ? `
			<div class="pa-import-options">
				<label>${esc(__('Status'))}
					<select id="pa-import-status"><option value="Draft">${esc(__('Draft'))}</option><option value="Published">${esc(__('Published'))}</option></select>
				</label>
				<label>${esc(__('Visibility'))}
					<select id="pa-import-visibility"><option value="Private">${esc(__('Private'))}</option><option value="Shared">${esc(__('Shared'))}</option><option value="Public">${esc(__('Public'))}</option></select>
				</label>
				<label id="pa-import-roles-wrap" hidden>${esc(__('Roles (comma separated)'))}
					<input type="text" id="pa-import-roles" placeholder="PA User, Sales Manager">
				</label>
				<button type="button" class="btn btn-primary btn-sm" id="pa-import-go"><i class="ph ph-download-simple" aria-hidden="true"></i> ${esc(__('Import'))}</button>
			</div>` : ''}`;
		const visibility = qs('#pa-import-visibility', result);
		if (visibility) {
			offs.push(on(visibility, 'change', () => {
				qs('#pa-import-roles-wrap', result).hidden = visibility.value !== 'Shared';
			}));
		}
		const go = qs('#pa-import-go', result);
		if (go) {
			offs.push(on(go, 'click', async () => {
				go.disabled = true;
				const roles = (qs('#pa-import-roles', result)?.value || '').split(',').map((r) => r.trim()).filter(Boolean);
				let res;
				try {
					res = await call(IMPORT, {
						file_url: fileUrl,
						status: qs('#pa-import-status', result).value,
						visibility: visibility.value,
						shared_roles: JSON.stringify(roles),
					}, { silent: true });
				} catch (err) {
					log.error('skill import', err);
					res = null;
				}
				if (!res || !res.success) {
					go.disabled = false;
					toast.error((res && res.error) || __('The package could not be imported.'));
					return;
				}
				toast.success(__('Skill {0} imported', [res.skill_id]));
				panel.close('done');
				if (onDone) onDone(res);
			}));
		}
	}));
	return panel;
}

export async function exportSkill(skillId) {
	let res;
	try {
		res = await call(EXPORT, { skill_id: skillId }, { silent: true });
	} catch (err) {
		log.error('skill export', err);
	}
	if (!res || !res.success) {
		toast.error((res && res.error) || __('The package could not be exported.'));
		return;
	}
	const link = document.createElement('a');
	link.href = res.file_url;
	link.download = res.file_name;
	document.body.appendChild(link);
	link.click();
	link.remove();
}
