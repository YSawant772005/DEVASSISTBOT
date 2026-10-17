<script setup lang="ts">
/**
 * Compact application top bar.
 *
 * Every control performs a real action: the nav switches the main workspace,
 * "New chat" starts a fresh conversation, and the status pill reflects the
 * live backend health probe.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Code2, FileText, LayoutGrid, Menu, MessageSquarePlus, Moon, Settings, Sun } from 'lucide-vue-next'

import type { AppView } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const settingsRef = ref<HTMLElement | null>(null)
const settingsOpen = ref(false)

const navItems: { id: AppView; label: string; icon: typeof FileText }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquarePlus },
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'examples', label: 'Examples', icon: LayoutGrid },
]

const connection = computed(() => {
  switch (documents.state.connection) {
    case 'online':
      return { label: 'Backend online', dot: 'bg-ok' }
    case 'degraded':
      return { label: 'Backend degraded', dot: 'bg-warn' }
    case 'offline':
      return { label: 'Backend offline', dot: 'bg-danger' }
    default:
      return { label: 'Checking backend…', dot: 'bg-faint' }
  }
})

function onDocumentClick(event: MouseEvent): void {
  if (settingsRef.value && !settingsRef.value.contains(event.target as Node)) {
    settingsOpen.value = false
  }
}

function startNewChat(): void {
  chat.newChat()
  ui.setView('chat')
}

onMounted(() => document.addEventListener('click', onDocumentClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick, true))
</script>

<template>
  <header
    class="relative z-30 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-surface/90 px-2.5 backdrop-blur-md sm:px-4"
  >
    <!-- Mobile: open navigation drawer -->
    <button
      type="button"
      class="icon-btn lg:hidden"
      aria-label="Open navigation"
      @click="ui.toggleNav(true)"
    >
      <Menu class="h-4 w-4" aria-hidden="true" />
    </button>

    <!-- Brand -->
    <button
      type="button"
      class="flex min-w-0 items-center gap-2.5 rounded-lg px-1 py-1 text-left"
      aria-label="DevAssist home"
      @click="ui.setView('chat')"
    >
      <span
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm"
        style="background-image: linear-gradient(135deg, #7657ff 0%, #438cff 100%)"
        aria-hidden="true"
      >
        <Code2 class="h-4 w-4" />
      </span>
      <span class="hidden min-w-0 leading-tight sm:block">
        <span class="block truncate text-[0.95rem] font-semibold tracking-tight text-ink">
          DevAssist
        </span>
        <span class="block truncate text-[0.65rem] text-faint">Programming assistant</span>
      </span>
    </button>

    <!-- Primary navigation -->
    <nav class="ml-1 hidden items-center gap-0.5 md:flex" aria-label="Primary">
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        class="btn btn-ghost !px-3 !py-1.5"
        :class="ui.state.view === item.id ? 'bg-accent-soft !text-ink' : ''"
        :aria-current="ui.state.view === item.id ? 'page' : undefined"
        @click="ui.setView(item.id)"
      >
        <component :is="item.icon" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ item.label }}
      </button>
    </nav>

    <div class="flex-1" />

    <!-- Connection status -->
    <span
      class="hidden items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-1 lg:inline-flex"
      :title="connection.label"
    >
      <span class="dot" :class="connection.dot" aria-hidden="true" />
      <span class="text-[0.675rem] text-muted">{{ connection.label }}</span>
    </span>

    <!-- New chat -->
    <button
      type="button"
      class="btn btn-soft hidden !py-1.5 sm:inline-flex"
      @click="startNewChat"
    >
      <MessageSquarePlus class="h-3.5 w-3.5" aria-hidden="true" />
      <span class="hidden lg:inline">New chat</span>
      <span class="sr-only lg:hidden">New chat</span>
    </button>

    <!-- Theme toggle -->
    <button
      type="button"
      class="icon-btn"
      :aria-label="ui.state.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
      :title="ui.state.theme === 'dark' ? 'Light theme' : 'Dark theme'"
      @click="ui.toggleTheme()"
    >
      <Sun v-if="ui.state.theme === 'dark'" class="h-4 w-4" aria-hidden="true" />
      <Moon v-else class="h-4 w-4" aria-hidden="true" />
    </button>

    <!-- Settings -->
    <div ref="settingsRef" class="relative">
      <button
        type="button"
        class="icon-btn"
        aria-label="Open settings"
        :aria-expanded="settingsOpen || ui.state.showSettings ? 'true' : 'false'"
        aria-haspopup="menu"
        @click.stop="settingsOpen = !settingsOpen"
      >
        <Settings class="h-4 w-4" aria-hidden="true" />
      </button>

      <div
        v-if="settingsOpen"
        role="menu"
        class="panel animate-fade-up absolute right-0 top-[2.6rem] w-56 p-1.5 shadow-2xl"
      >
        <button
          type="button"
          role="menuitem"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-muted hover:bg-surface-2 hover:text-ink"
          @click="settingsOpen = false; ui.mutableState.showSettings = true"
        >
          <Settings class="h-3.5 w-3.5" aria-hidden="true" /> Configuration &amp; status
        </button>
        <button
          type="button"
          role="menuitem"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-muted hover:bg-surface-2 hover:text-ink"
          @click="settingsOpen = false; ui.toggleTheme()"
        >
          <Sun v-if="ui.state.theme === 'dark'" class="h-3.5 w-3.5" aria-hidden="true" />
          <Moon v-else class="h-3.5 w-3.5" aria-hidden="true" />
          {{ ui.state.theme === 'dark' ? 'Light theme' : 'Dark theme' }}
        </button>
        <p class="mt-1 border-t border-line px-2.5 pb-1 pt-2 text-[0.65rem] leading-relaxed text-faint">
          The Groq key stays on the backend. Nothing here is sent to the browser.
        </p>
      </div>
    </div>
  </header>
</template>
