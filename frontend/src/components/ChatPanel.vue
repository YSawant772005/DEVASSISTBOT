<script setup lang="ts">
/**
 * Focused chat workspace: compact header, conversation area and composer.
 *
 * No hero banner is shown once a conversation exists; the conversation gets the
 * available space. The header keeps only a document indicator and a couple of
 * real controls.
 */
import { computed, ref } from 'vue'
import { Database, Eraser, PanelRightOpen, Sparkles } from 'lucide-vue-next'

import ChatComposer from '@/components/ChatComposer.vue'
import MessageList from '@/components/MessageList.vue'
import WelcomeState from '@/components/WelcomeState.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const listRef = ref<InstanceType<typeof MessageList> | null>(null)

const messages = computed(() => chat.activeMessages.value)
const hasMessages = computed(() => messages.value.length > 0)
const documentCount = computed(() => documents.state.documents.length)

const connectionLabel = computed(() => {
  switch (chat.state.socketStatus) {
    case 'open':
      return { text: 'Live', dot: 'bg-ok' }
    case 'connecting':
      return { text: 'Connecting…', dot: 'bg-warn animate-pulse-soft' }
    case 'closed':
      return { text: 'Idle', dot: 'bg-faint' }
    case 'error':
      return { text: 'Disconnected', dot: 'bg-danger' }
    default:
      return { text: 'Ready', dot: 'bg-faint' }
  }
})

const conversationTitle = computed(() => chat.activeConversation.value?.title ?? 'New conversation')

function onSend(text: string): void {
  void chat.sendMessage(text)
  listRef.value?.scrollToLatest()
}

function onSelectExample(prompt: string): void {
  ui.setPendingExample(prompt)
}

function onInspect(messageId: string): void {
  chat.inspectMessage(messageId)
  ui.toggleContext(true, 'sources')
}
</script>

<template>
  <section class="flex min-w-0 flex-1 flex-col bg-canvas" aria-label="Chat workspace">
    <!-- Compact header -->
    <header
      class="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-canvas/80 px-3 backdrop-blur-md sm:px-5"
    >
      <span
        class="flex h-6 w-6 items-center justify-center rounded-md bg-accent-soft text-accent-2"
        aria-hidden="true"
      >
        <Sparkles class="h-3.5 w-3.5" />
      </span>
      <h1 class="min-w-0 flex-1 truncate text-sm font-semibold text-ink" :title="conversationTitle">
        {{ conversationTitle }}
      </h1>

      <span
        class="hidden items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 sm:inline-flex"
        title="Streaming connection status"
      >
        <span class="dot" :class="connectionLabel.dot" aria-hidden="true" />
        <span class="text-[0.65rem] text-muted">{{ connectionLabel.text }}</span>
      </span>

      <!-- Knowledge base indicator -->
      <button
        type="button"
        class="hidden items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[0.65rem] text-muted transition-colors hover:border-line-2 hover:text-ink md:inline-flex"
        title="Open the knowledge base"
        @click="ui.setView('documents')"
      >
        <Database class="h-3 w-3 text-accent-2" aria-hidden="true" />
        Knowledge base · {{ documentCount }} {{ documentCount === 1 ? 'document' : 'documents' }}
      </button>

      <button
        type="button"
        class="icon-btn"
        aria-label="Clear this conversation"
        title="Clear conversation"
        :disabled="!hasMessages"
        @click="chat.clearActiveConversation()"
      >
        <Eraser class="h-4 w-4" aria-hidden="true" />
      </button>

      <button
        type="button"
        class="icon-btn"
        :class="ui.state.contextOpen ? 'bg-accent-soft text-accent' : ''"
        aria-label="Toggle sources and context panel"
        :aria-pressed="ui.state.contextOpen ? 'true' : 'false'"
        title="Sources and context"
        @click="ui.toggleContext(undefined, 'sources')"
      >
        <PanelRightOpen class="h-4 w-4" aria-hidden="true" />
      </button>
    </header>

    <!-- Conversation or welcome homepage -->
    <div class="flex min-h-0 flex-1 flex-col">
      <MessageList
        v-if="hasMessages"
        ref="listRef"
        :messages="messages"
        @retry="chat.retryLast()"
        @inspect="onInspect"
      />
      <div v-else class="min-h-0 flex-1 overflow-y-auto">
        <WelcomeState @select="onSelectExample" />
      </div>
    </div>

    <ChatComposer
      :is-generating="chat.state.isGenerating"
      @send="onSend"
      @stop="chat.stopGeneration()"
    />
  </section>
</template>
