<script setup lang="ts">
/**
 * Examples view: a gallery of pre-written programming prompts.
 *
 * Selecting one inserts it into the composer in the chat view, so the user can
 * edit it before sending. All entries are static, clearly-labelled starters.
 */
import { computed, ref } from 'vue'
import { Lightbulb, Search } from 'lucide-vue-next'

import { EXAMPLE_GALLERY, PROMPT_CARDS, type PromptCard } from '@/data/promptCards'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

const query = ref('')

const all: PromptCard[] = [...PROMPT_CARDS, ...EXAMPLE_GALLERY]

const filtered = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return all
  return all.filter(
    (card) =>
      card.title.toLowerCase().includes(term) ||
      card.description.toLowerCase().includes(term) ||
      card.prompt.toLowerCase().includes(term),
  )
})

function useCard(card: PromptCard): void {
  ui.setPendingExample(card.prompt)
  ui.setView('chat')
}
</script>

<template>
  <div class="min-w-0 flex-1 overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-4xl px-4 py-9 sm:px-8 sm:py-12">
      <header>
        <span class="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted">
          <Lightbulb class="h-3 w-3 text-accent-2" aria-hidden="true" />
          Prompt gallery
        </span>
        <h1 class="mt-4 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">
          Ready-to-use programming prompts
        </h1>
        <p class="mt-2 max-w-xl text-sm leading-relaxed text-muted">
          Start from a real, editable prompt. Selecting one opens it in the composer so you can
          adapt it to your code before sending.
        </p>
      </header>

      <div class="relative mt-6 max-w-md">
        <Search
          class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
          aria-hidden="true"
        />
        <input
          v-model="query"
          type="search"
          class="field !py-2.5 pl-9 text-sm"
          placeholder="Search prompts"
          aria-label="Search example prompts"
        />
      </div>

      <div v-if="!filtered.length" class="mt-8 rounded-xl border border-dashed border-line-2 bg-surface px-5 py-8 text-center">
        <p class="text-sm font-medium text-ink">No prompts match “{{ query }}”.</p>
        <p class="mt-1 text-xs text-muted">Try a different keyword, or write your own below.</p>
        <button type="button" class="btn btn-soft mt-4" @click="query = ''; ui.setView('chat')">
          Open the composer
        </button>
      </div>

      <div v-else class="mt-7 grid gap-3 sm:grid-cols-2">
        <button
          v-for="(card, index) in filtered"
          :key="card.id"
          type="button"
          class="prompt-card animate-fade-up"
          :style="{ animationDelay: `${Math.min(index, 8) * 45}ms` }"
          @click="useCard(card)"
        >
          <span class="prompt-card__icon">
            <component :is="card.icon" class="h-5 w-5" aria-hidden="true" />
          </span>
          <span class="block">
            <span class="block text-sm font-semibold text-ink">{{ card.title }}</span>
            <span class="mt-0.5 block text-xs leading-relaxed text-muted">
              {{ card.description }}
            </span>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
