<script setup lang="ts">
/** Determinate progress bar driven by real upload progress events. */
const props = defineProps<{
  value: number
  tone?: 'accent' | 'ok' | 'danger'
}>()

const tones = {
  accent: 'bg-accent',
  ok: 'bg-ok',
  danger: 'bg-danger',
} as const
</script>

<template>
  <div
    class="h-1.5 w-full overflow-hidden rounded-full bg-surface-3"
    role="progressbar"
    :aria-valuenow="props.value"
    aria-valuemin="0"
    aria-valuemax="100"
  >
    <div
      class="progress-fill h-full rounded-full transition-[width] duration-200"
      :class="tones[props.tone ?? 'accent']"
      :style="{ width: `${Math.max(0, Math.min(100, props.value))}%` }"
    />
  </div>
</template>
