<script setup lang="ts">
/**
 * Dedicated document-management view.
 *
 * A spacious page for the upload + retrieval lifecycle: drag-and-drop, real
 * per-file status, searchable rows and confirmed destructive actions.
 */
import { computed, onMounted } from 'vue'
import { AlertTriangle, RefreshCw } from 'lucide-vue-next'

import DocumentList from '@/components/DocumentList.vue'
import DocumentUploader from '@/components/DocumentUploader.vue'
import { useDocumentsStore } from '@/stores/documents'

const documents = useDocumentsStore()

const totalChunks = computed(() => documents.state.totalChunks)
const documentCount = computed(() => documents.state.documents.length)

onMounted(() => {
  void documents.refresh()
  void documents.checkHealth()
})
</script>

<template>
  <div class="min-w-0 flex-1 overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-4xl px-4 py-9 sm:px-8 sm:py-12">
      <!-- Page header -->
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">
            Your knowledge base
          </h1>
          <p class="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            Upload technical files once and DevAssist will cite them in its answers. Files are
            chunked, embedded locally and indexed for retrieval.
          </p>
        </div>

        <button type="button" class="btn btn-soft" @click="documents.refresh(); documents.checkHealth()">
          <RefreshCw class="h-3.5 w-3.5" aria-hidden="true" />
          Refresh
        </button>
      </header>

      <!-- Real counts, never fabricated -->
      <dl
        v-if="documentCount"
        class="mt-6 flex flex-wrap gap-6 border-y border-line py-4"
      >
        <div>
          <dt class="text-[0.7rem] uppercase tracking-wide text-faint">Documents</dt>
          <dd class="mt-0.5 text-lg font-semibold text-ink">{{ documentCount }}</dd>
        </div>
        <div>
          <dt class="text-[0.7rem] uppercase tracking-wide text-faint">Indexed chunks</dt>
          <dd class="mt-0.5 text-lg font-semibold text-ink">{{ totalChunks }}</dd>
        </div>
        <div>
          <dt class="text-[0.7rem] uppercase tracking-wide text-faint">Retrieval</dt>
          <dd class="mt-0.5 text-lg font-semibold text-ink">
            top {{ documents.state.health?.limits.top_k ?? '—' }}
          </dd>
        </div>
      </dl>

      <!-- Upload -->
      <div class="mt-7">
        <DocumentUploader />
      </div>

      <!-- Warnings from /health -->
      <div v-if="documents.state.health?.warnings.length" class="mt-5 space-y-2">
        <p
          v-for="warning in documents.state.health.warnings"
          :key="warning"
          class="flex items-start gap-2 rounded-xl border border-warn/30 bg-warn-soft px-4 py-2.5 text-xs leading-relaxed text-warn"
        >
          <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {{ warning }}
        </p>
      </div>

      <!-- List -->
      <div class="mt-8">
        <DocumentList />
      </div>

      <p class="mt-8 text-[0.7rem] leading-relaxed text-faint">
        The index lives in backend memory: restarting the server clears it. Only PDF, TXT and
        Markdown files up to 5 MB are accepted.
      </p>
    </div>
  </div>
</template>
