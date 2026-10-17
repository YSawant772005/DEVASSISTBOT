<script setup lang="ts">
/**
 * Markdown rendering with syntax-highlighted, copyable code blocks.
 *
 * Raw HTML from the model is escaped (markdown-it ``html: false``), so the
 * rendered HTML can be bound with ``v-html`` safely.
 */
import { computed, ref, watch } from 'vue'

import { copyToClipboard } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()

const html = computed(() => renderMarkdown(props.content))

/** Announced to screen readers after a successful copy. */
const announcement = ref('')
let announceTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.content,
  () => {
    announcement.value = ''
  },
)

function onContainerClick(event: MouseEvent): void {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-copy-code]')
  if (!button) return

  const code = button.closest('.code-block')?.querySelector('code')
  if (!code) return

  void copyToClipboard(code.textContent ?? '').then((ok) => {
    if (!ok) return
    button.dataset.copied = 'true'
    const original = button.textContent ?? 'Copy'
    button.textContent = 'Copied!'
    announcement.value = 'Code copied to clipboard.'
    if (announceTimer) clearTimeout(announceTimer)
    announceTimer = setTimeout(() => {
      button.dataset.copied = 'false'
      button.textContent = original
      announcement.value = ''
    }, 1600)
  })
}
</script>

<template>
  <div>
    <!-- eslint-disable-next-line vue/no-v-html -- markdown-it escapes raw HTML (html: false) -->
    <div class="md-body" v-html="html" @click="onContainerClick" />
    <span class="sr-only" role="status" aria-live="polite">{{ announcement }}</span>
  </div>
</template>
