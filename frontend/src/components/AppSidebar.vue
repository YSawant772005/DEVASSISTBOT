<script setup lang="ts">
/**
 * Collapsible left navigation.
 *
 * Holds the primary workspace links, session conversations (in-memory only) and
 * a compact knowledge-base indicator. Detailed document management lives in the
 * Documents view, so this panel stays intentionally light. The width is animated
 * on collapse so the layout never jumps.
 */
import { computed, ref } from 'vue'
import {
  ChevronsLeft,
  ChevronsRight,
  Database,
  FileText,
  History,
  LayoutGrid,
  MessageSquare,
  MessageSquarePlus,
  Search,
  Trash2,
  X,
} from 'lucide-vue-next'

import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore, type AppView } from '@/stores/ui'
import { relativeTime } from '@/utils/format'

const props = withDefaults(defineProps<{ collapsed?: boolean; inDrawer?: boolean }>(), {
  collapsed: false,
  inDrawer: false,
})

const emit = defineEmits<{ 'toggle-collapse': []; close: [] }>()

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const pendingRemoval = ref<string | null>(null)

const navItems: { id: AppView; label: string; icon: typeof FileText }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'examples', label: 'Examples', icon: LayoutGrid },
]

const filtered = computed(() => {
  const query = ui.state.conversationQuery.trim().toLowerCase()
  const list = chat.state.conversations
  if (!query) return list
  return list.filter((conversation) => {
    if (conversation.title.toLowerCase().includes(query)) return true
    return conversation.messages.some((message) => message.content.toLowerCase().includes(query))
  })
})

const documentCount = computed(() => documents.state.documents.length)

function onSelect(id: string): void {
  chat.selectConversation(id)
  ui.setView('chat')
  if (props.inDrawer) emit('close')
}

function requestRemove(id: string): void {
  if (pendingRemoval.value !== id) {
    pendingRemoval.value = id
    return
  }
  pendingRemoval.value = null
  chat.removeConversation(id)
}

function newChat(): void {
  chat.newChat()
  ui.setView('chat')
  if (props.inDrawer) emit('close')
}

function onSearch(event: Event): void {
  ui.mutableState.conversationQuery = (event.target as HTMLInputElement).value
}
</script>

<template>
  <nav
    class="flex h-full flex-col border-r border-line bg-surface transition-[width] duration-200 ease-out"
    :class="collapsed ? 'w-[4.25rem] items-center px-2 py-3' : 'w-[16.5rem]'"
    :aria-label="collapsed ? 'Primary navigation' : 'Conversations and knowledge base'"
  >
    <!-- Collapsed rail --------------------------------------------------- -->
    <template v-if="collapsed">
      <button
        type="button"
        class="icon-btn"
        aria-label="Expand navigation"
        title="Expand navigation"
        @click="emit('toggle-collapse')"
      >
        <ChevronsRight class="h-4 w-4" aria-hidden="true" />
      </button>

      <button
        type="button"
        class="icon-btn mt-1 bg-accent-soft text-accent"
        aria-label="New chat"
        title="New chat"
        @click="newChat"
      >
        <MessageSquarePlus class="h-4 w-4" aria-hidden="true" />
      </button>

      <div class="mt-1 space-y-0.5">
        <button
          v-for="item in navItems"
          :key="item.id"
          type="button"
          class="icon-btn"
          :class="ui.state.view === item.id ? 'bg-accent-soft text-accent' : ''"
          :aria-label="item.label"
          :aria-current="ui.state.view === item.id ? 'page' : undefined"
          :title="item.label"
          @click="ui.setView(item.id)"
        >
          <component :is="item.icon" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <button
        type="button"
        class="icon-btn relative mt-1"
        aria-label="Documents"
        title="Documents"
        @click="ui.setView('documents')"
      >
        <Database class="h-4 w-4" aria-hidden="true" />
        <span
          v-if="documentCount"
          class="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[0.6rem] font-semibold text-white"
        >
          {{ documentCount }}
        </span>
      </button>
    </template>

    <!-- Expanded --------------------------------------------------------- -->
    <template v-else>
      <div class="flex items-center justify-between gap-2 px-3 pb-1.5 pt-3">
        <span class="text-[0.7rem] font-semibold uppercase tracking-wider text-faint">Workspace</span>
        <button
          v-if="inDrawer"
          type="button"
          class="icon-btn"
          aria-label="Close navigation"
          @click="emit('close')"
        >
          <X class="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          v-else
          type="button"
          class="icon-btn hidden lg:inline-flex"
          aria-label="Collapse navigation"
          title="Collapse navigation"
          @click="emit('toggle-collapse')"
        >
          <ChevronsLeft class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div class="px-3 pb-2">
        <button type="button" class="btn btn-primary w-full" @click="newChat">
          <MessageSquarePlus class="h-4 w-4" aria-hidden="true" />
          New chat
        </button>
      </div>

      <!-- Primary navigation (keeps every workspace reachable on small screens) -->
      <nav class="space-y-0.5 px-3 pb-3" aria-label="Workspaces">
        <button
          v-for="item in navItems"
          :key="item.id"
          type="button"
          class="nav-item"
          :class="ui.state.view === item.id ? 'is-active' : ''"
          :aria-current="ui.state.view === item.id ? 'page' : undefined"
          @click="ui.setView(item.id)"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
          {{ item.label }}
        </button>
      </nav>

      <!-- Knowledge base indicator -->
      <div class="px-3 pb-2">
        <button
          type="button"
          class="flex w-full items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-2.5 py-2 text-left transition-colors hover:border-line-2"
          @click="ui.setView('documents')"
        >
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent-2"
            aria-hidden="true"
          >
            <Database class="h-3.5 w-3.5" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-xs font-medium text-ink">Knowledge base</span>
            <span class="block truncate text-[0.675rem] text-faint">
              {{ documentCount }} {{ documentCount === 1 ? 'document' : 'documents' }}
            </span>
          </span>
        </button>
      </div>

      <!-- Recent conversations -->
      <div class="flex min-h-0 flex-1 flex-col px-3">
        <div class="flex items-center justify-between gap-2 pb-1.5">
          <span class="section-label">
            <History class="h-3 w-3" aria-hidden="true" />
            Recent
          </span>
        </div>

        <div v-if="chat.state.conversations.length" class="relative pb-2">
          <Search
            class="pointer-events-none absolute left-2.5 top-[0.55rem] h-3.5 w-3.5 text-faint"
            aria-hidden="true"
          />
          <input
            type="search"
            class="field !py-1.5 pl-8 text-xs"
            placeholder="Search conversations"
            aria-label="Search session conversations"
            :value="ui.state.conversationQuery"
            @input="onSearch"
          />
        </div>

        <div class="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 pb-2">
          <p
            v-if="!chat.state.conversations.length"
            class="rounded-lg border border-dashed border-line px-3 py-3 text-[0.7rem] leading-relaxed text-faint"
          >
            Conversations live in this browser tab only. Start a chat and it will appear here.
          </p>

          <p v-else-if="!filtered.length" class="px-2 py-3 text-[0.7rem] text-faint">
            No conversations match “{{ ui.state.conversationQuery }}”.
          </p>

          <ul v-else class="space-y-0.5">
            <li
              v-for="conversation in filtered"
              :key="conversation.id"
              class="group flex items-center gap-1 rounded-lg border border-transparent pr-1 transition-colors"
              :class="
                conversation.id === chat.state.activeId
                  ? 'border-accent/40 bg-accent-soft'
                  : 'hover:border-line hover:bg-surface-2'
              "
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left"
                :aria-current="conversation.id === chat.state.activeId ? 'true' : undefined"
                @click="onSelect(conversation.id)"
              >
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-xs text-ink">{{ conversation.title }}</span>
                  <span class="block text-[0.625rem] text-faint">
                    {{ conversation.messages.length }} msgs · {{ relativeTime(conversation.updatedAt) }}
                  </span>
                </span>
              </button>
              <button
                type="button"
                class="icon-btn h-6 w-6 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                :class="pendingRemoval === conversation.id ? '!text-danger !opacity-100' : ''"
                :aria-label="`Delete conversation: ${conversation.title}`"
                :title="pendingRemoval === conversation.id ? 'Click again to confirm' : 'Delete conversation'"
                @click="requestRemove(conversation.id)"
              >
                <Trash2 class="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          </ul>
        </div>
      </div>

      <p class="border-t border-line px-3 py-2.5 text-[0.625rem] leading-relaxed text-faint">
        Chat history and documents live in memory only — refreshing clears chats, restarting the
        backend clears the index.
      </p>
    </template>
  </nav>
</template>
