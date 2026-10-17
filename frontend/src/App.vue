<script setup lang="ts">
/**
 * DevAssist application shell.
 *
 * The layout adapts to the task: a collapsible left navigation, the active
 * workspace (chat / documents / examples) and an optional right context panel.
 * Tablet and mobile turn the side panels into drawers.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import AppSidebar from '@/components/AppSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ContextPanel from '@/components/ContextPanel.vue'
import DocumentsView from '@/components/DocumentsView.vue'
import PromptGallery from '@/components/PromptGallery.vue'
import SettingsDialog from '@/components/SettingsDialog.vue'
import TopNav from '@/components/TopNav.vue'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const documents = useDocumentsStore()
const ui = useUiStore()

const isDesktop = useMediaQuery('(min-width: 1024px)')
const hasInlineContext = useMediaQuery('(min-width: 1280px)')

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  if (ui.state.showSettings) {
    ui.mutableState.showSettings = false
    return
  }
  if (ui.state.navOpen) ui.toggleNav(false)
  if (ui.state.contextOpen) ui.toggleContext(false)
}

onMounted(() => {
  ui.initTheme()
  void documents.refresh()
  void documents.checkHealth()
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  chat.reset()
})
</script>

<template>
  <div class="flex h-full flex-col bg-canvas">
    <TopNav />

    <div class="flex min-h-0 flex-1">
      <!-- Desktop left navigation -->
      <div v-if="isDesktop" class="shrink-0 transition-[width] duration-200 ease-out">
        <AppSidebar
          :collapsed="ui.state.navCollapsed"
          @toggle-collapse="ui.toggleNavCollapsed()"
        />
      </div>

      <!-- Main workspace -->
      <main class="flex min-w-0 flex-1">
        <ChatPanel v-if="ui.state.view === 'chat'" />
        <DocumentsView v-else-if="ui.state.view === 'documents'" />
        <PromptGallery v-else />
      </main>

      <!-- Desktop context panel (chat only, optional) -->
      <Transition name="panel">
        <div
          v-if="hasInlineContext && ui.state.view === 'chat' && ui.state.contextOpen"
          class="w-[21rem] shrink-0"
        >
          <ContextPanel />
        </div>
      </Transition>
    </div>

    <!-- Mobile / tablet navigation drawer -->
    <Transition name="fade">
      <div
        v-if="!isDesktop && ui.state.navOpen"
        class="fixed inset-0 z-40"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="ui.toggleNav(false)" />
        <div
          class="animate-slide-in-left absolute inset-y-0 left-0 w-[18rem] max-w-[85vw] border-r border-line bg-surface shadow-2xl"
        >
          <AppSidebar in-drawer @close="ui.toggleNav(false)" />
        </div>
      </div>
    </Transition>

    <!-- Mobile / tablet context drawer -->
    <Transition name="fade">
      <div
        v-if="!hasInlineContext && ui.state.view === 'chat' && ui.state.contextOpen"
        class="fixed inset-0 z-40"
        role="dialog"
        aria-modal="true"
        aria-label="Sources and context"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="ui.toggleContext(false)" />
        <div
          class="animate-slide-in-right absolute inset-y-0 right-0 w-[19rem] max-w-[88vw] border-l border-line bg-surface shadow-2xl"
        >
          <ContextPanel />
        </div>
      </div>
    </Transition>

    <!-- Settings dialog -->
    <SettingsDialog v-if="ui.state.showSettings" @close="ui.mutableState.showSettings = false" />

    <span class="sr-only" aria-live="polite">
      {{ ui.state.navOpen ? 'Navigation opened' : '' }}
    </span>
  </div>
</template>
