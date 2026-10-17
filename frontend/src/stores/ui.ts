/** UI shell state: theme, active view, responsive panels and dialogs. */

import { reactive, readonly } from 'vue'

const THEME_KEY = 'devassist-theme'

type Theme = 'dark' | 'light'
export type AppView = 'chat' | 'documents' | 'examples'
export type ContextTab = 'sources' | 'followups' | 'context'

interface UiState {
  theme: Theme
  /** Which primary workspace is visible in the main area. */
  view: AppView
  /** Desktop: the left navigation is collapsed to a narrow rail. */
  navCollapsed: boolean
  /** Small screens: the left navigation drawer is open. */
  navOpen: boolean
  /** Right context panel visibility (inline on desktop, drawer otherwise). */
  contextOpen: boolean
  contextTab: ContextTab
  showSettings: boolean
  /** Bumped to tell the composer to insert an example prompt. */
  pendingExample: string | null
  /** Filter text for the recent-conversations list. */
  conversationQuery: string
  /** Filter text for the documents list. */
  documentQuery: string
}

const state = reactive<UiState>({
  theme: 'dark',
  view: 'chat',
  navCollapsed: false,
  navOpen: false,
  contextOpen: false,
  contextTab: 'sources',
  showSettings: false,
  pendingExample: null,
  conversationQuery: '',
  documentQuery: '',
})

function applyTheme(): void {
  const isLight = state.theme === 'light'
  document.documentElement.classList.toggle('light', isLight)
  document.documentElement.classList.toggle('dark', !isLight)
}

function initTheme(): void {
  let stored: string | null = null
  try {
    stored = localStorage.getItem(THEME_KEY)
  } catch {
    stored = null
  }
  state.theme = stored === 'light' || stored === 'dark' ? stored : 'dark'
  applyTheme()
}

function toggleTheme(): void {
  state.theme = state.theme === 'dark' ? 'light' : 'dark'
  try {
    localStorage.setItem(THEME_KEY, state.theme)
  } catch {
    // Storage may be unavailable (private mode); theme still applies in memory.
  }
  applyTheme()
}

function setView(view: AppView): void {
  state.view = view
  state.navOpen = false
  if (view !== 'chat') state.contextOpen = false
}

/** Open the context panel, optionally on a specific tab. */
function toggleContext(force?: boolean, tab?: ContextTab): void {
  if (tab) state.contextTab = tab
  state.contextOpen = force ?? !state.contextOpen
}

function setContextTab(tab: ContextTab): void {
  state.contextTab = tab
  state.contextOpen = true
}

function toggleNavCollapsed(force?: boolean): void {
  state.navCollapsed = force ?? !state.navCollapsed
}

function toggleNav(force?: boolean): void {
  state.navOpen = force ?? !state.navOpen
}

function setPendingExample(prompt: string): void {
  state.pendingExample = prompt
}

function consumePendingExample(): string | null {
  const prompt = state.pendingExample
  state.pendingExample = null
  return prompt
}

function reset(): void {
  state.view = 'chat'
  state.navCollapsed = false
  state.navOpen = false
  state.contextOpen = false
  state.contextTab = 'sources'
  state.showSettings = false
  state.pendingExample = null
  state.conversationQuery = ''
  state.documentQuery = ''
}

export function useUiStore() {
  return {
    state: readonly(state),
    get mutableState() {
      return state
    },
    initTheme,
    toggleTheme,
    setView,
    toggleContext,
    setContextTab,
    toggleNavCollapsed,
    toggleNav,
    setPendingExample,
    consumePendingExample,
    reset,
  }
}
