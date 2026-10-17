<script setup lang="ts">
/** Compact scope card describing what DevAssist helps with. */
import { Braces, FileCode2, Layers, ShieldCheck } from 'lucide-vue-next'

const capabilities = [
  { label: 'Programming & debugging', icon: Braces },
  { label: 'Algorithms & data structures', icon: Layers },
  { label: 'Architecture & system design', icon: ShieldCheck },
  { label: 'Technical documentation', icon: FileCode2 },
]
</script>

<template>
  <section aria-labelledby="scope-heading" class="rounded-xl border border-line bg-surface-2 p-3">
    <h2 id="scope-heading" class="section-label mb-2">Programming-only assistant</h2>
    <ul class="space-y-1.5">
      <li v-for="capability in capabilities" :key="capability.label" class="flex items-start gap-2">
        <component
          :is="capability.icon"
          class="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent"
          aria-hidden="true"
        />
        <span class="text-[0.72rem] leading-snug text-muted">{{ capability.label }}</span>
      </li>
    </ul>
    <p class="mt-2.5 border-t border-line pt-2 text-[0.62rem] leading-relaxed text-faint">
      Off-topic requests are politely declined. Topic filtering is best-effort prompt guidance,
      not a guarantee.
    </p>
  </section>
</template>
