<script setup lang="ts">
/**
 * Starter prompts. These are clearly presented as suggestions, not generated
 * follow-ups; clicking one sends it through the real chat flow.
 */
import { MessageSquareDashed, Sparkles } from 'lucide-vue-next'

import { FOLLOW_UP_SUGGESTIONS } from '@/config'

const emit = defineEmits<{ ask: [prompt: string] }>()

function ask(prompt: string): void {
  emit('ask', prompt)
}
</script>

<template>
  <section aria-labelledby="followups-heading">
    <h2 id="followups-heading" class="section-label mb-2">
      <Sparkles class="h-3 w-3" aria-hidden="true" />
      Suggested questions
    </h2>
    <ul class="space-y-1.5">
      <li v-for="suggestion in FOLLOW_UP_SUGGESTIONS" :key="suggestion">
        <button
          type="button"
          class="panel panel-hover w-full px-3 py-2 text-left text-[0.72rem] leading-relaxed text-muted transition-colors hover:border-accent/40 hover:text-ink"
          @click="ask(suggestion)"
        >
          {{ suggestion }}
        </button>
      </li>
    </ul>
    <p class="mt-2 flex items-start gap-1.5 text-[0.62rem] leading-relaxed text-faint">
      <MessageSquareDashed class="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
      These are pre-written starters, not generated suggestions.
    </p>
  </section>
</template>
