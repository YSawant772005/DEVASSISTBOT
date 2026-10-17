<script setup lang="ts">
/**
 * Chat composer.
 *
 * Multiline input with Enter to send and Shift+Enter for a newline, a real file
 * attachment (the same ingestion pipeline), an explicit character limit and a
 * stop control while generating.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { Paperclip, Send, Square } from 'lucide-vue-next'

import ProgressBar from '@/components/ui/ProgressBar.vue'
import { MAX_QUESTION_CHARS } from '@/config'
import { validateFile } from '@/services/api'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ isGenerating: boolean }>()

const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const documents = useDocumentsStore()
const ui = useUiStore()

const textarea = ref<HTMLTextAreaElement | null>(null)
const attachmentInput = ref<HTMLInputElement | null>(null)
const draft = ref('')
const error = ref<string | null>(null)

const canSend = computed(() => draft.value.trim().length > 0 && !props.isGenerating)
const overLimit = computed(() => draft.value.length > MAX_QUESTION_CHARS)
const showCounter = computed(() => draft.value.length > MAX_QUESTION_CHARS * 0.75)

/** Latest real attachment progress, shown above the field. */
const latestAttachment = computed(() => documents.state.jobs[0] ?? null)

/** Document count surfaced in the disclaimer line. */
const documentCount = computed(() => documents.state.documents.length)

function resize(): void {
  const element = textarea.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 220)}px`
}

watch(draft, async () => {
  resize()
  await nextTick()
  resize()
})

function submit(): void {
  const text = draft.value.trim()
  if (!text || props.isGenerating) return
  if (overLimit.value) {
    error.value = `Your message is ${text.length.toLocaleString()} characters. The limit is ${MAX_QUESTION_CHARS.toLocaleString()}.`
    return
  }
  error.value = null
  emit('send', text)
  draft.value = ''
  nextTick(resize)
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function openAttachmentPicker(): void {
  attachmentInput.value?.click()
}

function onAttachmentSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return

  const firstInvalid = files.map(validateFile).find((result) => !result.ok)
  if (firstInvalid && !firstInvalid.ok) {
    error.value = firstInvalid.message
    return
  }
  error.value = null
  void documents.uploadFiles(files)
}

// Selecting a prompt from the welcome page or the gallery fills the composer.
watch(
  () => ui.state.pendingExample,
  async (prompt) => {
    if (!prompt) return
    draft.value = prompt
    error.value = null
    ui.consumePendingExample()
    await nextTick()
    textarea.value?.focus()
    resize()
  },
)

defineExpose({ focus: () => textarea.value?.focus() })
</script>

<template>
  <div class="border-t border-line bg-canvas/90 px-3 pb-4 pt-3 backdrop-blur-md sm:px-6">
    <div class="mx-auto w-full max-w-3xl">
      <!-- Attachment feedback -->
      <div
        v-if="latestAttachment && (latestAttachment.state === 'uploading' || latestAttachment.state === 'processing')"
        class="mb-2 flex items-center gap-2.5 rounded-lg border border-line bg-surface px-3 py-2"
      >
        <Paperclip class="h-3.5 w-3.5 shrink-0 text-accent-2" aria-hidden="true" />
        <span class="min-w-0 flex-1 truncate text-xs text-ink">
          {{ latestAttachment.filename }}
          <span class="text-faint">
            · {{ latestAttachment.state === 'uploading' ? `${latestAttachment.progress}%` : 'indexing…' }}
          </span>
        </span>
        <ProgressBar
          v-if="latestAttachment.state === 'uploading'"
          :value="latestAttachment.progress"
          class="w-24 shrink-0"
        />
      </div>

      <div
        class="rounded-2xl border bg-surface transition-colors"
        :class="error || overLimit ? 'border-danger/50' : 'border-line focus-within:border-accent/60'"
      >
        <label for="chat-input" class="sr-only">Ask a programming question</label>
        <textarea
          id="chat-input"
          ref="textarea"
          v-model="draft"
          rows="1"
          class="block max-h-56 w-full resize-none bg-transparent px-4 pb-1.5 pt-3.5 text-sm leading-relaxed text-ink outline-none placeholder:text-faint"
          placeholder="Ask a programming question or paste your code..."
          @keydown="onKeydown"
          @input="resize"
        />

        <div class="flex items-center gap-2 px-2.5 pb-2.5 pt-1">
          <button
            type="button"
            class="icon-btn"
            aria-label="Attach a document (PDF, TXT or MD)"
            title="Attach a document"
            @click="openAttachmentPicker"
          >
            <Paperclip class="h-4 w-4" aria-hidden="true" />
          </button>

          <span class="hidden text-[0.65rem] text-faint sm:inline">
            <kbd class="rounded border border-line bg-surface px-1 py-0.5 font-mono text-[0.6rem]">Enter</kbd>
            to send ·
            <kbd class="rounded border border-line bg-surface px-1 py-0.5 font-mono text-[0.6rem]">Shift+Enter</kbd>
            newline
          </span>

          <span class="flex-1" />

          <span
            v-if="showCounter"
            class="text-[0.65rem]"
            :class="overLimit ? 'text-danger' : 'text-faint'"
          >
            {{ draft.length.toLocaleString() }} / {{ MAX_QUESTION_CHARS.toLocaleString() }}
          </span>

          <button
            v-if="isGenerating"
            type="button"
            class="btn btn-danger"
            aria-label="Stop generating"
            @click="emit('stop')"
          >
            <Square class="h-3.5 w-3.5" aria-hidden="true" />
            Stop
          </button>

          <button
            v-else
            type="button"
            class="btn btn-primary"
            :disabled="!canSend"
            aria-label="Send message"
            @click="submit"
          >
            <Send class="h-3.5 w-3.5" aria-hidden="true" />
            Send
          </button>
        </div>
      </div>

      <p v-if="error" class="mt-2 text-[0.7rem] leading-snug text-danger" role="alert">
        {{ error }}
      </p>
      <p v-else-if="overLimit" class="mt-2 text-[0.7rem] leading-snug text-danger" role="alert">
        Messages are limited to {{ MAX_QUESTION_CHARS.toLocaleString() }} characters.
      </p>
      <p v-else class="mt-2 text-[0.65rem] leading-snug text-faint">
        DevAssist can make mistakes — review and test generated code before using it.
        <span v-if="documentCount" class="text-muted">
          · Answers are grounded in your {{ documentCount }}
          {{ documentCount === 1 ? 'uploaded document' : 'uploaded documents' }} when relevant.
        </span>
      </p>

      <input
        ref="attachmentInput"
        type="file"
        multiple
        accept=".pdf,.txt,.md,.markdown"
        class="sr-only"
        aria-label="Attach a document"
        @change="onAttachmentSelected"
      />
    </div>
  </div>
</template>
