<template>
	<img
		class="aida-avatar"
		:class="[`aida-avatar-${size}`, { 'aida-avatar-float': float }, extraClass]"
		:src="iconUrl"
		alt="AIDA"
		:width="px"
		:height="px"
		draggable="false"
	/>
</template>

<script setup>
import { computed } from "vue";

const iconUrl = "/assets/pibiassistant/chat/widget/aida-icon.svg";

// Same props the legacy CSS robot accepted so existing call sites keep working;
// only size, float and extraClass affect the AIDA character.
const props = defineProps({
	size: { type: String, default: "md" },
	mood: { type: String, default: null },
	staticIdle: { type: Boolean, default: false },
	float: { type: Boolean, default: false },
	showBody: { type: Boolean, default: true },
	showArms: { type: Boolean, default: false },
	showShadow: { type: Boolean, default: false },
	track: { type: Boolean, default: false },
	extraClass: { type: String, default: "" },
});

const SIZES = { xs: 20, sm: 32, md: 48, lg: 80 };
const px = computed(() => SIZES[props.size] || SIZES.md);
</script>

<style scoped>
.aida-avatar {
	display: inline-block;
	flex: none;
	border-radius: 50%;
	user-select: none;
	box-shadow: 0 2px 8px rgba(70, 130, 180, 0.3);
}

.aida-avatar-float {
	animation: aida-avatar-float 3s ease-in-out infinite;
}

@keyframes aida-avatar-float {
	0%,
	100% {
		transform: translateY(0);
	}
	50% {
		transform: translateY(-4px);
	}
}

@media (prefers-reduced-motion: reduce) {
	.aida-avatar-float {
		animation: none;
	}
}
</style>
