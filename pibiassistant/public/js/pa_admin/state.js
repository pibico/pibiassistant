const defaults = () => ({
    toggleInProgress: {},
    refreshInProgress: false,
    autoRefreshEnabled: true,
    viewMode: 'plugins',
    activeTab: 'tools',
    availableRoles: [],
    openConfigPanels: {},
    promptsData: [],
    skillsData: [],
    toolsData: [],
    lastRefreshedAt: null,
    chatEnabled: null,
    counts: { tools: null, prompts: null, skills: null },
});

export const state = defaults();

export function resetState() {
    Object.assign(state, defaults());
}

export function hasToggleInProgress() {
    return Object.keys(state.toggleInProgress).length > 0;
}

export function beginToggle(key) {
    if (state.toggleInProgress[key]) return false;
    state.toggleInProgress[key] = true;
    state.autoRefreshEnabled = false;
    return true;
}

export function endToggle(key) {
    delete state.toggleInProgress[key];
    state.autoRefreshEnabled = true;
}
