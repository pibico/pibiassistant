<template>
	<!-- Message footer: model, tokens in/out, speed, time + routing chip + credits -->
	<div
		v-if="showTimestamps || showRouting || (!isUser && (message.credits_used || hasUsage || message.timestamp))"
		class="message-footer"
	>
		<span v-if="!isUser && modelLabel" class="message-model" :title="__('Model used')">{{ modelLabel }}</span>
		<span v-if="!isUser && hasUsage" class="message-usage">
			<span :title="__('Input tokens')">↑{{ message.prompt_tokens ?? "–" }}</span>
			<span :title="__('Output tokens')">↓{{ message.completion_tokens ?? "–" }}</span>
		</span>
		<span v-if="!isUser && tokensPerSecond" class="message-speed" :title="__('Output speed')">{{ tokensPerSecond }} {{ __("tokens/s") }}</span>
		<span v-if="(showTimestamps || !isUser) && message.timestamp" class="message-timestamp">{{ formattedTime }}</span>
		<button
			v-if="chipText"
			ref="routingTrigger"
			type="button"
			class="message-routing-chip"
			:title="routingLine"
			:aria-expanded="String(routingOpen)"
			aria-haspopup="true"
			@click="routingOpen = !routingOpen"
		>{{ chipText }}</button>
		<button
			v-if="creditsIsDoor"
			ref="routingTrigger"
			type="button"
			class="message-credits message-credits-door"
			:title="creditsDoorTitle"
			:aria-expanded="String(routingOpen)"
			aria-haspopup="true"
			@click="routingOpen = !routingOpen"
		>{{ creditsLabel }}</button>
		<span v-else-if="!isUser && message.credits_used" class="message-credits" :title="creditsTooltip">{{ creditsLabel }}</span>
	</div>
	<RoutingPanel
		v-if="showRouting && routingOpen"
		:receipt="message.routing"
		:model-name="routingModelName"
		@close="closeRouting"
	/>
</template>

<script setup>
import { computed, ref } from "vue";
import { usePreferences } from "@/composables/usePreferences";
import { useModelStore } from "@/stores/modelStore";
import RoutingPanel from "./RoutingPanel.vue";
import { __ } from "@/utils/i18n";
import {
	CHIP_DEFAULT,
	creditsLabel as formatCredits,
	hasRouting,
	routingChipLabel,
	routingHeadline,
} from "./routingCopy.js";

const props = defineProps({
	message: { type: Object, required: true },
	isUser: { type: Boolean, default: false },
});

const { preferences } = usePreferences();
const modelStore = useModelStore();

const showTimestamps = computed(() => preferences.showTimestamps);
const modelLabel = computed(() => {
	const id = props.message.model || props.message.model_id;
	return id ? modelStore.modelDisplayName(id) || id : "";
});
const hasUsage = computed(
	() => props.message.prompt_tokens != null || props.message.completion_tokens != null
);
const tokensPerSecond = computed(() => {
	const out = Number(props.message.completion_tokens);
	const ms = Number(props.message.duration_ms);
	return out > 0 && ms > 0 ? (out / (ms / 1000)).toFixed(1) : "";
});
const routingOpen = ref(false);
const routingTrigger = ref(null);

// The guard stays `!isUser && ...`: get_session_messages returns the routing
// column for every row in the session regardless of role, so a bare
// `|| message.routing` would render the assistant footer on user bubbles.
const showRouting = computed(
	() =>
		!props.isUser && preferences.showRoutingChip && hasRouting(props.message)
);
const routingModelName = computed(() =>
	modelStore.modelDisplayName(props.message.routing?.selected_model)
);

// L0 is exception-only, so an ordinary turn leaves the footer the shape it had
// before auto mode: time and credits. The credits figure is then the door to
// the panel — "why did this cost that?" is the question the panel answers, so
// it needs no chip of its own, and one door beats two.
const chipText = computed(() => {
	if (!showRouting.value) return "";
	return (
		routingChipLabel(props.message.routing) ||
		(props.message.credits_used ? "" : CHIP_DEFAULT)
	);
});
const creditsIsDoor = computed(
	() =>
		showRouting.value &&
		!chipText.value &&
		Boolean(props.message.credits_used)
);
const routingLine = computed(() =>
	routingHeadline(
		props.message.routing,
		routingModelName.value,
		modelStore.modelDisplayName(props.message.routing?.fallback_from)
	)
);

function closeRouting() {
	routingOpen.value = false;
	// Focus returns to the control that opened it, not to the document.
	routingTrigger.value?.focus();
}

const formattedTime = computed(() => {
	if (!props.message.timestamp) return "";
	const date = new Date(props.message.timestamp);
	const now = new Date();
	const diffMs = now - date;
	const diffMin = Math.floor(diffMs / 60000);

	if (diffMin < 1) return "Just now";
	if (diffMin < 60) return `${diffMin}m ago`;

	const diffHours = Math.floor(diffMin / 60);
	if (diffHours < 24 && date.getDate() === now.getDate()) {
		return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
	}

	return date.toLocaleDateString([], {
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
});

const creditsLabel = computed(() => formatCredits(props.message.credits_used));

const creditsTooltip = computed(() => {
	// The display name, never the raw id: `claude-sonnet-4-5-20250929` is a
	// build stamp, and a member reading a bill has no use for it.
	const model = modelStore.modelDisplayName(props.message.model);
	return model
		? `Billed on the text in and out of this turn, at ${model}'s rate.`
		: "Billed on the text going into and out of this turn.";
});

// The door names no model at all — the panel it opens does that properly, and
// a tooltip is not the place to introduce a codename nobody asked for.
const creditsDoorTitle = computed(
	() => "Billed on the text in and out of this turn. Click to see how it ran."
);
</script>

<style scoped>
.message-footer {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.125rem;
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	opacity: 0.8;
}

.message-usage {
	display: inline-flex;
	gap: 0.4rem;
}

.message-model,
.message-usage,
.message-speed,
.message-timestamp {
	font-variant-numeric: tabular-nums;
}

.message-timestamp {
	font-variant-numeric: tabular-nums;
}

/* Two doors to the same panel, never both at once: the chip when something
   worth naming happened, otherwise the credits figure itself. */
.message-routing-chip,
.message-credits-door {
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	color: inherit;
	cursor: pointer;
}

.message-routing-chip:hover,
.message-credits-door:hover {
	color: var(--ql-text-secondary);
	text-decoration: underline dotted;
}

.message-routing-chip:focus-visible,
.message-credits-door:focus-visible {
	outline: 1px solid var(--ql-accent);
	outline-offset: 2px;
	border-radius: var(--ql-radius-sm);
}

/* The footer is a middot-separated list; every item after the first gets one. */
.message-footer > * + *::before {
	content: "\00b7";
	margin-right: 0.5rem;
}
</style>
