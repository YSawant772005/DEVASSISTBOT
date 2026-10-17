<script setup lang="ts">
/**
 * Document upload for the Documents page.
 *
 * Drag-and-drop plus a real file picker, with live progress, indexing status
 * and clear failure feedback. Every state shown comes from the actual upload
 * pipeline — nothing is simulated.
 */
import { computed, ref } from 'vue'
import { CheckCircle2, FileUp, Loader2, UploadCloud, X } from 'lucide-vue-next'

import ProgressBar from '@/components/ui/ProgressBar.vue'
import { ALLOWED_EXTENSIONS_LABEL, MAX_UPLOAD_LABEL } from '@/config'
import { useDocumentsStore } from '@/stores/documents'

const documents = useDocumentsStore()

const isDragging = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)
const dragDepth = ref(0)

const activeJobs = computed(() => documents.state.jobs.filter((job) => job.state !== 'indexed'))
const indexedJobs = computed(() => documents.state.jobs.filter((job) => job.state === 'indexed'))

function openPicker(): void {
  inputRef.value?.click()
}

function onFilesSelected(event: Event): void {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files ?? [])
  if (files.length) void documents.uploadFiles(files)
  target.value = ''
}

function onDrop(event: DragEvent): void {
  isDragging.value = false
  dragDepth.value = 0
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length) void documents.uploadFiles(files)
}

function onDragEnter(event: DragEvent): void {
  if (!Array.from(event.dataTransfer?.types ?? []).includes('Files')) return
  dragDepth.value += 1
  isDragging.value = true
}

function onDragLeave(): void {
  dragDepth.value = Math.max(0, dragDepth.value - 1)
  if (dragDepth.value === 0) isDragging.value = false
}

function onDragOver(event: DragEvent): void {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

const stateLabel: Record<string, string> = {
  uploading: 'Uploading',
  processing: 'Indexing',
  indexed: 'Indexed',
  failed: 'Failed',
}
</script>

<template>
  <section aria-labelledby="upload-heading">
    <div
      class="panel relative flex min-h-[13rem] flex-col items-center justify-center gap-3 border-dashed px-6 py-9 text-center transition-colors"
      :class="isDragging ? 'border-accent bg-accent-soft' : 'border-line-2'"
      @dragenter="onDragEnter"
      @dragleave="onDragLeave"
      @dragover="onDragOver"
      @drop="onDrop"
    >
      <span
        class="flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface-3 transition-all"
        :class="isDragging ? 'scale-110 border-accent/50 text-accent-2' : 'text-accent-2'"
        aria-hidden="true"
      >
        <UploadCloud class="h-7 w-7" />
      </span>

      <div>
        <h2 id="upload-heading" class="text-base font-semibold text-ink">
          {{ isDragging ? 'Drop to upload' : 'Drag & drop files here' }}
        </h2>
        <p class="mt-1 text-xs text-muted">
          or
          <button
            type="button"
            class="font-medium text-accent-2 underline-offset-2 hover:underline"
            @click="openPicker"
          >
            click to browse
          </button>
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-center gap-2">
        <span class="chip">{{ ALLOWED_EXTENSIONS_LABEL }}</span>
        <span class="chip">Max {{ MAX_UPLOAD_LABEL }}</span>
      </div>

      <p class="max-w-md text-[0.7rem] leading-relaxed text-faint">
        Uploaded files are chunked, embedded with the local model and indexed so answers can be
        grounded in your own material.
      </p>

      <button type="button" class="btn btn-primary" @click="openPicker">
        <FileUp class="h-4 w-4" aria-hidden="true" />
        Upload files
      </button>

      <input
        ref="inputRef"
        type="file"
        multiple
        class="sr-only"
        accept=".pdf,.txt,.md,.markdown"
        aria-label="Upload documents"
        @change="onFilesSelected"
      />
    </div>

    <!-- Active jobs -->
    <ul v-if="activeJobs.length" class="mt-3 space-y-2" aria-live="polite">
      <li
        v-for="job in activeJobs"
        :key="job.id"
        class="animate-fade-up rounded-xl border px-4 py-3 transition-colors"
        :class="job.state === 'failed' ? 'border-danger/35 bg-danger-soft' : 'border-line bg-surface'"
      >
        <div class="flex items-center gap-3">
          <Loader2
            v-if="job.state !== 'failed'"
            class="h-4 w-4 shrink-0 animate-spin text-accent-2"
            aria-hidden="true"
          />
          <X v-else class="h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
          <span class="min-w-0 flex-1 truncate text-sm font-medium text-ink">{{ job.filename }}</span>
          <span
            class="shrink-0 text-[0.7rem] font-medium"
            :class="job.state === 'failed' ? 'text-danger' : 'text-faint'"
          >
            {{ stateLabel[job.state] }}
            <template v-if="job.state === 'uploading'"> · {{ job.progress }}%</template>
          </span>
          <button
            type="button"
            class="icon-btn h-7 w-7"
            :aria-label="`Dismiss upload notice for ${job.filename}`"
            @click="documents.dismissJob(job.id)"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <ProgressBar v-if="job.state === 'uploading'" :value="job.progress" class="mt-2.5" />
        <p v-if="job.state === 'failed'" class="mt-2 text-xs leading-snug text-danger">
          {{ job.message }}
        </p>
      </li>
    </ul>

    <!-- Confirmed uploads -->
    <ul v-if="indexedJobs.length" class="mt-3 space-y-2">
      <li
        v-for="job in indexedJobs"
        :key="job.id"
        class="animate-fade-up flex items-center gap-3 rounded-xl border border-ok/30 bg-ok-soft px-4 py-2.5"
      >
        <CheckCircle2 class="h-4 w-4 shrink-0 text-ok" aria-hidden="true" />
        <span class="min-w-0 flex-1 truncate text-sm text-ink">
          {{ job.filename }}
          <span class="text-faint">· {{ job.chunks }} chunks indexed</span>
        </span>
        <button
          type="button"
          class="icon-btn h-7 w-7"
          :aria-label="`Dismiss upload notice for ${job.filename}`"
          @click="documents.dismissJob(job.id)"
        >
          <X class="h-4 w-4" />
        </button>
      </li>
    </ul>

    <p
      v-if="documents.state.error"
      class="mt-3 rounded-xl border border-danger/35 bg-danger-soft px-4 py-3 text-xs leading-snug text-danger"
      role="alert"
    >
      {{ documents.state.error }}
    </p>
  </section>
</template>
