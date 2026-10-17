<script setup lang="ts">
/**
 * Optional right-hand context panel with three sections: real sources for the
 * current answer, useful follow-up prompts, and the current assistant context.
 *
 * The panel is closed by default and can be dismissed to reclaim horizontal
 * space.
 */
import { computed } from 'vue'
import { Info, Sparkles, X } from 'lucide-vue-next'

import AssistantInfoCard from '@/components/AssistantInfoCard.vue'
import FollowUpPanel from '@/components/FollowUpPanel.vue'
import SourcePanel from '@/components/SourcePanel.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'
import type { ContextTab } from '@/stores/ui'

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const tabs: { id: ContextTab; label: string }[] = [
  { id: 'sources', label: 'Sources' },
  { id: 'followups', label: 'Follow-ups' },
  { id: 'context', label: 'Context' },
]

const sourceCount = computed(() => chat.currentSources.value.length)
const documentCount = computed(() => documents.state.documents.length)

function ask(prompt: string): void {
  void chat.sendMessage(prompt)
  ui.toggleContext(false)
}
</script>

<template>
  <aside
    class="flex h-full w-full flex-col overflow-hidden border-line bg-surface"
    aria-label="Sources and context"
  >
    <!-- Header + tabs -->
    <header class="flex items-center gap-2 border-b border-line px-4 py-3">
      <h2 class="mr-auto text-sm font-semibold text-ink">Context</h2>
      <button
        type="button"
        class="icon-btn h-8 w-8"
        aria-label="Close context panel"
        title="Close"
        @click="ui.toggleContext(false)"
      >
        <X class="h-4 w-4" aria-hidden="true" />
      </button>
    </header>

    <div class="px-3 pt-3">
      <div class="segmented w-full" role="tablist" aria-label="Context sections">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          class="segmented__item flex-1"
          :class="ui.state.contextTab === tab.id ? 'is-active' : ''"
          :aria-selected="ui.state.contextTab === tab.id ? 'true' : 'false'"
          @click="ui.setContextTab(tab.id)"
        >
          {{ tab.label }}
          <span v-if="tab.id === 'sources' && sourceCount" class="text-faint">· {{ sourceCount }}</span>
        </button>
      </div>
    </div>

    <!-- Body -->
    <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-4">
      <SourcePanel v-if="ui.state.contextTab === 'sources'" />
      <FollowUpPanel v-else-if="ui.state.contextTab === 'followups'" @ask="ask" />

      <div v-else class="space-y-4">
        <AssistantInfoCard />

        <!-- Real application state only -->
        <section aria-labelledby="runtime-heading">
          <h3 id="runtime-heading" class="section-label mb-2">
            <Info class="h-3 w-3" aria-hidden="true" />
            Runtime
          </h3>
          <dl class="space-y-1.5 text-xs">
            <div class="flex items-center justify-between gap-3">
              <dt class="text-muted">Knowledge base</dt>
              <dd class="text-ink">
                {{ documentCount }} {{ documentCount === 1 ? 'document' : 'documents' }}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-muted">Indexed chunks</dt>
              <dd class="text-ink">{{ documents.state.totalChunks }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-muted">Connection</dt>
              <dd class="flex items-center gap-1.5 text-ink">
                <span class="dot" :class="documents.state.connection === 'online' ? 'bg-ok' : documents.state.connection === 'offline' ? 'bg-danger' : 'bg-faint'" aria-hidden="true" />
                {{ documents.state.connection }}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-muted">Scope</dt>
              <dd class="text-ink">Programming only</dd>
            </div>
          </dl>
        </section>

        <p class="flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-[0.7rem] leading-relaxed text-muted">
          <Sparkles class="mt-0.5 h-3 w-3 shrink-0 text-accent-2" aria-hidden="true" />
          Chat history stays in this tab; the index lives in backend memory until restart.
        </p>
      </div>
    </div>
  </aside>
</template>
