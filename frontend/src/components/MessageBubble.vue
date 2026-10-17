<script setup lang="ts">
/**
 * A single conversation turn.
 *
 * Assistant answers are intentionally not boxed into heavy cards — typography
 * and spacing carry the hierarchy instead. User turns get a compact aligned
 * bubble so the two sides read distinctly. Sources, errors and copy/retry
 * affordances are attached below the content.
 */
import { computed, ref } from 'vue'
import { AlertTriangle, BookOpen, Check, Copy, RefreshCw, Sparkles, User } from 'lucide-vue-next'

import MarkdownMessage from '@/components/MarkdownMessage.vue'
import type { ChatMessage } from '@/types/chat'
import { copyToClipboard, formatTime } from '@/utils/format'

const props = defineProps<{
  message: ChatMessage
  showSources?: boolean
}>()

const emit = defineEmits<{
  retry: []
  inspect: [messageId: string]
}>()

const isAssistant = computed(() => props.message.role === 'assistant')
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

const stageLabel = computed(() => {
  switch (props.message.stage) {
    case 'retrieving':
      return 'Searching your documents…'
    case 'generating':
      return 'Thinking…'
    default:
      return 'Thinking…'
  }
})

function copyMessage(): void {
  void copyToClipboard(props.message.content).then((ok) => {
    if (!ok) return
    copied.value = true
    if (copiedTimer) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => (copied.value = false), 1600)
  })
}

function scorePercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}
</script>

<template>
  <article
    class="group flex animate-fade-up gap-3 sm:gap-3.5"
    :class="isAssistant ? '' : 'flex-row-reverse'"
    :aria-label="isAssistant ? 'DevAssist response' : 'Your message'"
  >
    <!-- Avatar -->
    <span
      class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm"
      :class="isAssistant ? 'border border-transparent' : 'border border-line bg-surface-2 text-muted'"
      :style="
        isAssistant ? 'background-image: linear-gradient(135deg, #7657ff 0%, #438cff 100%)' : ''
      "
      aria-hidden="true"
    >
      <Sparkles v-if="isAssistant" class="h-4 w-4" />
      <User v-else class="h-4 w-4" />
    </span>

    <div class="min-w-0 flex-1" :class="isAssistant ? '' : 'flex flex-col items-end'">
      <header
        class="mb-1.5 flex items-center gap-2"
        :class="isAssistant ? '' : 'flex-row-reverse'"
      >
        <span class="text-xs font-semibold text-ink">{{ isAssistant ? 'DevAssist' : 'You' }}</span>
        <span class="text-[0.625rem] text-faint">{{ formatTime(message.createdAt) }}</span>
      </header>

      <!-- Body -->
      <!-- Assistant: borderless content so long answers stay readable. -->
      <div v-if="isAssistant" class="max-w-full">
        <p
          v-if="!message.content && message.status === 'streaming'"
          class="flex items-center gap-2 text-xs text-muted"
        >
          <span class="thinking-dot" aria-hidden="true" />
          {{ stageLabel }}
        </p>
        <MarkdownMessage v-else :content="message.content" />
        <span
          v-if="message.status === 'streaming' && message.content"
          class="stream-caret"
          aria-hidden="true"
        />
      </div>

      <!-- User: compact right-aligned bubble. -->
      <div
        v-else
        class="max-w-[min(46rem,85%)] rounded-2xl rounded-tr-sm border border-accent/25 bg-accent-soft px-4 py-2.5"
      >
        <pre
          class="whitespace-pre-wrap break-words font-sans text-[0.9rem] leading-relaxed"
        >{{ message.content }}</pre>
      </div>

      <!-- Stopped notice -->
      <p v-if="message.status === 'stopped'" class="mt-1.5 text-[0.675rem] italic text-faint">
        Generation stopped.
      </p>

      <!-- Error + retry -->
      <div
        v-if="message.status === 'error' && message.error"
        class="mt-2 rounded-lg border border-danger/35 bg-danger-soft px-3 py-2"
        role="alert"
      >
        <p class="flex items-start gap-2 text-xs leading-relaxed text-danger">
          <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{{ message.error.message }}</span>
        </p>
        <button type="button" class="btn btn-soft mt-2 !py-1" @click="emit('retry')">
          <RefreshCw class="h-3 w-3" aria-hidden="true" />
          Retry
        </button>
      </div>

      <!-- Sources -->
      <div v-if="message.sources?.length" class="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span class="inline-flex items-center gap-1 text-[0.625rem] font-medium uppercase tracking-wide text-faint">
          <BookOpen class="h-3 w-3" aria-hidden="true" />
          Sources
        </span>
        <button
          v-for="source in message.sources"
          :key="`${source.doc_id}-${source.chunk_index}`"
          type="button"
          class="chip max-w-[14rem] transition-colors hover:border-accent/50 hover:text-ink"
          :title="`Inspect source: ${source.filename}, chunk ${source.chunk_index}`"
          @click="emit('inspect', message.id)"
        >
          <span class="truncate">{{ source.filename }}</span>
          <span class="text-faint">· ch {{ source.chunk_index + 1 }}</span>
          <span class="text-accent-2">{{ scorePercent(source.score) }}%</span>
        </button>
      </div>

      <div
        v-if="message.status !== 'streaming'"
        class="mt-1.5 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
      >
        <button
          v-if="message.content"
          type="button"
          class="icon-btn h-7 w-7"
          :aria-label="copied ? 'Copied' : 'Copy message'"
          :title="copied ? 'Copied' : 'Copy'"
          @click="copyMessage"
        >
          <Check v-if="copied" class="h-3.5 w-3.5 text-ok" />
          <Copy v-else class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  </article>
</template>
