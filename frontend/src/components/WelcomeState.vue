<script setup lang="ts">
/**
 * Welcome homepage.
 *
 * Shown whenever there is no active conversation. A new user immediately sees
 * how to start chatting, what DevAssist is for, and how to ground answers in
 * their own documents. Every action is real: prompt cards fill the composer,
 * the upload action runs the normal ingestion pipeline, and recent
 * conversations come from the in-memory chat store.
 */
import { computed, ref } from 'vue'
import { ArrowRight, Database, FileUp, MessageSquare, Sparkles } from 'lucide-vue-next'

import { PROMPT_CARDS } from '@/data/promptCards'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'
import { relativeTime } from '@/utils/format'

const emit = defineEmits<{ select: [prompt: string] }>()

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const fileInput = ref<HTMLInputElement | null>(null)

const documentCount = computed(() => documents.state.documents.length)

const recent = computed(() =>
  [...chat.state.conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 4),
)

function openPicker(): void {
  fileInput.value?.click()
}

function onFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return
  void documents.uploadFiles(files)
  ui.setView('documents')
}

function onSelect(prompt: string): void {
  emit('select', prompt)
}

function openConversation(id: string): void {
  chat.selectConversation(id)
  ui.setView('chat')
}
</script>

<template>
  <div class="mx-auto w-full max-w-[68rem] px-4 py-10 sm:px-6 sm:py-14">
    <!-- Introduction -->
    <div class="animate-fade-up">
      <span
        class="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted"
      >
        <Sparkles class="h-3 w-3 text-accent-2" aria-hidden="true" />
        AI programming assistant
        <span class="text-faint">·</span>
        <span class="text-cyan">RAG enabled</span>
      </span>

      <h1 class="mt-5 max-w-3xl text-3xl font-bold leading-tight tracking-tight text-ink sm:text-[2.6rem]">
        Build, debug, and <span class="accent-text">understand code.</span>
      </h1>

      <p class="mt-3 max-w-2xl text-sm leading-relaxed text-muted sm:text-base">
        Ask programming questions, explore technical concepts, and get answers grounded in your
        uploaded documentation.
      </p>
    </div>

    <!-- Quick-start cards -->
    <div class="mt-8 grid gap-3 sm:grid-cols-2">
      <button
        v-for="(card, index) in PROMPT_CARDS"
        :key="card.id"
        type="button"
        class="prompt-card animate-fade-up"
        :style="{ animationDelay: `${80 + index * 55}ms` }"
        @click="onSelect(card.prompt)"
      >
        <span class="prompt-card__icon">
          <component :is="card.icon" class="h-5 w-5" aria-hidden="true" />
        </span>
        <span class="block">
          <span class="block text-sm font-semibold text-ink">{{ card.title }}</span>
          <span class="mt-0.5 block text-xs leading-relaxed text-muted">{{ card.description }}</span>
        </span>
        <span class="mt-0.5 flex items-center gap-1 text-[0.7rem] font-medium text-accent-2">
          Try it
          <ArrowRight class="h-3 w-3" aria-hidden="true" />
        </span>
      </button>
    </div>

    <!-- Knowledge base guidance -->
    <div class="mt-8 animate-fade-up" style="animation-delay: 320ms">
      <div
        v-if="!documentCount"
        class="flex flex-col gap-3 rounded-xl border border-dashed border-line-2 bg-surface px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex items-start gap-3">
          <span
            class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-2"
            aria-hidden="true"
          >
            <FileUp class="h-4 w-4" />
          </span>
          <p class="text-xs leading-relaxed text-muted">
            <span class="font-medium text-ink">No documents indexed yet.</span>
            Upload a PDF, TXT or Markdown file (max 5 MB) to get answers grounded in your own
            documentation — otherwise DevAssist answers from general programming knowledge.
          </p>
        </div>
        <button type="button" class="btn btn-soft shrink-0" @click="openPicker">
          <FileUp class="h-3.5 w-3.5" aria-hidden="true" />
          Upload documents
        </button>
      </div>

      <div
        v-else
        class="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3"
      >
        <span class="flex items-center gap-2.5 text-xs text-muted">
          <span class="dot bg-ok" aria-hidden="true" />
          <span class="font-medium text-ink">
            {{ documentCount }} {{ documentCount === 1 ? 'document' : 'documents' }} ready
          </span>
          for grounded answers.
        </span>
        <button
          type="button"
          class="btn btn-ghost !py-1.5 text-xs"
          @click="ui.setView('documents')"
        >
          <Database class="h-3.5 w-3.5" aria-hidden="true" />
          Manage
        </button>
      </div>

      <p v-if="documents.state.error" class="mt-2 text-[0.7rem] text-danger" role="alert">
        {{ documents.state.error }}
      </p>

      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".pdf,.txt,.md,.markdown"
        class="sr-only"
        aria-label="Upload documents"
        @change="onFiles"
      />
    </div>

    <!-- Recent conversations, or onboarding when empty -->
    <section class="mt-8 animate-fade-up" style="animation-delay: 380ms">
      <h2 class="section-label mb-3">
        <MessageSquare class="h-3 w-3" aria-hidden="true" />
        {{ recent.length ? 'Recent conversations' : 'Getting started' }}
      </h2>

      <ul v-if="recent.length" class="grid gap-2 sm:grid-cols-2">
        <li v-for="conversation in recent" :key="conversation.id">
          <button
            type="button"
            class="panel panel-hover flex w-full items-center gap-3 px-3.5 py-2.5 text-left"
            @click="openConversation(conversation.id)"
          >
            <MessageSquare class="h-4 w-4 shrink-0 text-faint" aria-hidden="true" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-xs font-medium text-ink">{{ conversation.title }}</span>
              <span class="block text-[0.65rem] text-faint">
                {{ conversation.messages.length }} messages · {{ relativeTime(conversation.updatedAt) }}
              </span>
            </span>
          </button>
        </li>
      </ul>

      <div v-else class="flex flex-col gap-2 text-xs leading-relaxed text-muted sm:flex-row sm:gap-6">
        <p class="flex items-start gap-2">
          <span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-2" aria-hidden="true" />
          Pick a quick-start card above, or type your own question below.
        </p>
        <p class="flex items-start gap-2">
          <span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
          Upload documentation first to get answers cited from your own files.
        </p>
      </div>
    </section>
  </div>
</template>
