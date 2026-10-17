/** Reactive media-query hook. */

import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export function useMediaQuery(query: string): Ref<boolean> {
  const matched = ref(
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : false,
  )
  let mql: MediaQueryList | null = null

  const update = () => {
    matched.value = mql?.matches ?? false
  }

  onMounted(() => {
    if (typeof window.matchMedia !== 'function') return
    mql = window.matchMedia(query)
    update()
    mql.addEventListener('change', update)
  })

  onBeforeUnmount(() => {
    mql?.removeEventListener('change', update)
  })

  return matched
}

/** Auto-scroll behaviour: follows new content only when already near the end. */
export function useAutoScroll(container: Ref<HTMLElement | null>, threshold = 140) {
  const isNearBottom = ref(true)

  const handleScroll = () => {
    const element = container.value
    if (!element) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    isNearBottom.value = distance <= threshold
  }

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const element = container.value
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior })
  }

  onMounted(() => {
    container.value?.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
  })

  onBeforeUnmount(() => {
    container.value?.removeEventListener('scroll', handleScroll)
  })

  return { isNearBottom, scrollToBottom, handleScroll }
}
