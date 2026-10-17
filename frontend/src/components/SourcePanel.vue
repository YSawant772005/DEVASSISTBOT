<script setup lang="ts">
/**
 * Real retrieved sources for the inspected answer.
 *
 * Every value shown (filename, chunk index, similarity, preview) comes from
 * the backend's ``sources`` WebSocket event — nothing is fabricated.
 */
import { computed, ref } from 'vue'
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-vue-next'

import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

const sources = computed(() => chat.currentSources.value)
const expanded = ref<string | null>(null)

function toggle(docId: string, chunk: number): void {
  const key = `${docId}:${chunk}`
  expanded.value = expanded.value === key ? null : key
}

function percent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}
</script>

<template>
  <section aria-labelledby="sources-heading">
    <header class="mb-2.5 flex items-center justify-between gap-2">
      <h2 id="sources-heading" class="section-label">
        <BookOpen class="h-3 w-3" aria-hidden="true" />
        Response sources
      </h2>
      <span v-if="sources.length" class="text-[0.625rem] text-faint">
        {{ sources.length }} {{ sources.length === 1 ? 'chunk' : 'chunks' }}
      </span>
    </header>

    <p
      v-if="!sources.length"
      class="rounded-lg border border-dashed border-line px-3 py-3 text-[0.72rem] leading-relaxed text-faint"
    >
      No document chunks were used for this answer — it came from general programming knowledge.
      Upload a document to ground answers in your own material.
    </p>

    <ul v-else class="space-y-2">
      <li
        v-for="source in sources"
        :key="`${source.doc_id}-${source.chunk_index}`"
        class="panel panel-hover overflow-hidden"
      >
        <div class="flex items-center gap-2 px-3 py-2">
          <span
            class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent"
            aria-hidden="true"
          >
            <FileText class="h-3 w-3" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-xs font-medium text-ink" :title="source.filename">
              {{ source.filename }}
            </span>
            <span class="block text-[0.625rem] text-faint">
              Chunk {{ source.chunk_index + 1 }} · {{ percent(source.score) }}% similar
            </span>
          </span>
          <button
            type="button"
            class="icon-btn h-6 w-6"
            :aria-expanded="expanded === `${source.doc_id}:${source.chunk_index}` ? 'true' : 'false'"
            :aria-label="`Toggle preview for ${source.filename} chunk ${source.chunk_index + 1}`"
            @click="toggle(source.doc_id, source.chunk_index)"
          >
            <ChevronDown
              v-if="expanded !== `${source.doc_id}:${source.chunk_index}`"
              class="h-3.5 w-3.5"
            />
            <ChevronUp v-else class="h-3.5 w-3.5" />
          </button>
        </div>

        <!-- Similarity bar reflects the score returned by FAISS -->
        <div class="mx-3 h-1 overflow-hidden rounded-full bg-surface-3">
          <div
            class="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
            :style="{ width: `${percent(source.score)}%` }"
          />
        </div>

        <p
          v-if="expanded !== `${source.doc_id}:${source.chunk_index}`"
          class="line-clamp-2 px-3 py-2 text-[0.7rem] leading-relaxed text-muted"
        >
          {{ source.preview }}
        </p>
        <pre
          v-else
          class="max-h-48 overflow-auto whitespace-pre-wrap break-words border-t border-line bg-surface-2 px-3 py-2 font-mono text-[0.68rem] leading-relaxed text-muted"
        >{{ source.preview }}</pre>
      </li>
    </ul>

    <p v-if="sources.length" class="mt-2 text-[0.62rem] leading-relaxed text-faint">
      Retrieved with the local embedding model and in-memory FAISS index. Similarity is cosine
      similarity (0–100%).
    </p>
  </section>
</template>
