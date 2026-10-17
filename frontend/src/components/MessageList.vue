<script setup lang="ts">
/**
 * Scrollable conversation area.
 *
 * Follows new content only when the reader is already near the bottom; a
 * "Jump to latest" control appears otherwise so reading history is not
 * interrupted by streaming.
 */
import { nextTick, ref, watch } from 'vue'
import { ArrowDown } from 'lucide-vue-next'

import MessageBubble from '@/components/MessageBubble.vue'
import { useAutoScroll } from '@/composables/useMediaQuery'
import type { ChatMessage } from '@/types/chat'

const props = defineProps<{ messages: ChatMessage[] }>()

const emit = defineEmits<{ retry: []; inspect: [messageId: string] }>()

const container = ref<HTMLElement | null>(null)
const { isNearBottom, scrollToBottom, handleScroll } = useAutoScroll(container)

watch(
  () => [props.messages.length, props.messages[props.messages.length - 1]?.content.length],
  async () => {
    await nextTick()
    if (isNearBottom.value) {
      scrollToBottom()
      // Re-measure after the smooth scroll settles so streaming keeps working.
      window.setTimeout(handleScroll, 250)
    }
  },
  { immediate: true },
)

defineExpose({
  scrollToLatest: () => scrollToBottom(),
})
</script>

<template>
  <div class="relative min-h-0 flex-1">
    <div ref="container" class="h-full overflow-y-auto px-4 py-5 sm:px-6">
      <div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
        <MessageBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
          @retry="emit('retry')"
          @inspect="(id) => emit('inspect', id)"
        />
      </div>
    </div>

    <button
      v-if="!isNearBottom && messages.length"
      type="button"
      class="btn btn-soft absolute bottom-3 left-1/2 -translate-x-1/2 shadow-lg"
      @click="scrollToBottom()"
    >
      <ArrowDown class="h-3.5 w-3.5" aria-hidden="true" />
      Jump to latest
    </button>
  </div>
</template>
