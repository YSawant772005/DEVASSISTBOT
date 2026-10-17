<script setup lang="ts">
/**
 * Indexed documents with search, per-file removal (click twice to confirm) and
 * a confirmed clear-all. Deletion calls the real backend operation and updates
 * the visible state on success.
 */
import { computed, ref } from 'vue'
import { CheckCircle2, FileCode2, FileText, Loader2, Search, Trash2 } from 'lucide-vue-next'

import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'
import { formatBytes } from '@/utils/format'

const documents = useDocumentsStore()
const ui = useUiStore()

const confirmingClear = ref(false)
const pendingRemoval = ref<string | null>(null)

const filtered = computed(() => {
  const query = ui.state.documentQuery.trim().toLowerCase()
  const list = documents.state.documents
  if (!query) return list
  return list.filter((doc) => doc.filename.toLowerCase().includes(query))
})

function iconFor(extension: string) {
  return extension === '.pdf' ? FileText : FileCode2
}

function onSearch(event: Event): void {
  ui.mutableState.documentQuery = (event.target as HTMLInputElement).value
}

async function confirmRemove(docId: string): Promise<void> {
  if (pendingRemoval.value !== docId) {
    pendingRemoval.value = docId
    return
  }
  pendingRemoval.value = null
  await documents.removeDocument(docId)
}

async function onClearAll(): Promise<void> {
  if (!confirmingClear.value) {
    confirmingClear.value = true
    return
  }
  confirmingClear.value = false
  await documents.clearAll()
}
</script>

<template>
  <section aria-labelledby="documents-heading" class="min-h-0">
    <header class="mb-3 flex flex-wrap items-center gap-3">
      <h2 id="documents-heading" class="section-label mr-auto">
        Indexed documents
        <span
          v-if="documents.state.documents.length"
          class="rounded-full bg-surface-3 px-1.5 py-px text-[0.6rem]"
        >
          {{ documents.state.documents.length }}
        </span>
      </h2>

      <div v-if="documents.state.documents.length" class="relative w-56 max-w-full">
        <Search
          class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint"
          aria-hidden="true"
        />
        <input
          type="search"
          class="field !py-1.5 pl-8 text-xs"
          placeholder="Search documents"
          aria-label="Search indexed documents"
          :value="ui.state.documentQuery"
          @input="onSearch"
        />
      </div>

      <button
        v-if="documents.state.documents.length"
        type="button"
        class="text-[0.7rem] font-medium transition-colors"
        :class="confirmingClear ? 'text-danger' : 'text-muted hover:text-ink'"
        @click="onClearAll"
      >
        {{ confirmingClear ? 'Confirm clear all?' : 'Clear all' }}
      </button>
    </header>

    <div
      v-if="documents.state.loading && !documents.state.documents.length"
      class="flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-5 text-sm text-muted"
    >
      <Loader2 class="h-4 w-4 animate-spin text-accent-2" aria-hidden="true" />
      Loading documents…
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!documents.state.documents.length"
      class="rounded-xl border border-dashed border-line-2 bg-surface px-5 py-8 text-center"
    >
      <p class="text-sm font-medium text-ink">Your knowledge base is empty</p>
      <p class="mx-auto mt-1.5 max-w-sm text-xs leading-relaxed text-muted">
        Upload a PDF, TXT or Markdown file above and DevAssist will ground its answers in your
        content — with real source citations.
      </p>
    </div>

    <!-- No search matches -->
    <div
      v-else-if="!filtered.length"
      class="rounded-xl border border-line bg-surface px-4 py-5 text-center text-sm text-muted"
    >
      No documents match “{{ ui.state.documentQuery }}”.
    </div>

    <!-- Rows -->
    <ul v-else class="overflow-hidden rounded-xl border border-line bg-surface">
      <li
        v-for="(doc, index) in filtered"
        :key="doc.doc_id"
        class="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2"
        :class="index ? 'border-t border-line' : ''"
      >
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-3 text-accent-2"
          aria-hidden="true"
        >
          <component :is="iconFor(doc.extension)" class="h-4 w-4" />
        </span>

        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm font-medium text-ink" :title="doc.filename">
            {{ doc.filename }}
          </span>
          <span class="mt-0.5 block text-[0.7rem] text-faint">
            {{ formatBytes(doc.size_bytes) }} · {{ doc.chunks }}
            {{ doc.chunks === 1 ? 'chunk' : 'chunks' }} · {{ doc.extension.replace('.', '').toUpperCase() }}
          </span>
        </span>

        <!-- Status: icon + label, not colour alone -->
        <span
          class="hidden items-center gap-1.5 rounded-full border border-ok/30 bg-ok-soft px-2.5 py-1 text-[0.65rem] font-medium text-ok sm:inline-flex"
        >
          <CheckCircle2 class="h-3 w-3" aria-hidden="true" />
          Indexed
        </span>

        <button
          type="button"
          class="icon-btn h-8 w-8 shrink-0"
          :class="pendingRemoval === doc.doc_id ? '!text-danger' : ''"
          :aria-label="`Remove ${doc.filename} from the index`"
          :title="pendingRemoval === doc.doc_id ? 'Click again to confirm removal' : 'Remove document'"
          @click="confirmRemove(doc.doc_id)"
        >
          <Trash2 class="h-4 w-4" aria-hidden="true" />
        </button>
      </li>
    </ul>
  </section>
</template>
