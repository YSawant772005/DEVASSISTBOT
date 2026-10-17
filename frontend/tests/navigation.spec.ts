import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from '@/App.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import DocumentList from '@/components/DocumentList.vue'
import PromptGallery from '@/components/PromptGallery.vue'
import TopNav from '@/components/TopNav.vue'
import { PROMPT_CARDS } from '@/data/promptCards'
import * as api from '@/services/api'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'
import type { Conversation, UploadedDocument } from '@/types/chat'

function makeDocument(overrides: Partial<UploadedDocument> = {}): UploadedDocument {
  return {
    doc_id: 'd1',
    filename: 'gateway.md',
    extension: '.md',
    size_bytes: 4096,
    chunks: 3,
    uploaded_at: new Date().toISOString(),
    ...overrides,
  }
}

function makeConversation(id: string, title: string): Conversation {
  return {
    id,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  }
}

beforeEach(() => {
  useUiStore().reset()
  useChatStore().reset()
  useDocumentsStore().reset()
})

describe('ui store navigation', () => {  it('switches the active workspace view', () => {
    const ui = useUiStore()
    expect(ui.state.view).toBe('chat')

    ui.setView('documents')
    expect(ui.state.view).toBe('documents')

    ui.setView('examples')
    expect(ui.state.view).toBe('examples')
    // Leaving chat also closes the context panel.
    expect(ui.state.contextOpen).toBe(false)
  })

  it('opens the context panel on a specific tab', () => {
    const ui = useUiStore()
    ui.toggleContext(true, 'followups')
    expect(ui.state.contextOpen).toBe(true)
    expect(ui.state.contextTab).toBe('followups')

    ui.setContextTab('context')
    expect(ui.state.contextTab).toBe('context')

    ui.toggleContext(false)
    expect(ui.state.contextOpen).toBe(false)
  })

  it('queues an example prompt for the composer exactly once', () => {
    const ui = useUiStore()
    ui.setPendingExample('Explain async/await')

    expect(ui.consumePendingExample()).toBe('Explain async/await')
    expect(ui.consumePendingExample()).toBeNull()
    expect(ui.state.pendingExample).toBeNull()
  })

  it('collapses and expands the left navigation', () => {
    const ui = useUiStore()
    expect(ui.state.navCollapsed).toBe(false)
    ui.toggleNavCollapsed()
    expect(ui.state.navCollapsed).toBe(true)
    ui.toggleNavCollapsed(false)
    expect(ui.state.navCollapsed).toBe(false)
  })
})

describe('TopNav', () => {
  it('moves between Chat, Documents and Examples', async () => {
    const ui = useUiStore()
    const wrapper = mount(TopNav)

    const nav = wrapper.get('nav[aria-label="Primary"]')
    const buttons = nav.findAll('button')
    expect(buttons.map((button) => button.text())).toEqual(['Chat', 'Documents', 'Examples'])

    await buttons[1]!.trigger('click')
    expect(ui.state.view).toBe('documents')

    await buttons[2]!.trigger('click')
    expect(ui.state.view).toBe('examples')

    wrapper.unmount()
  })

  it('starts a new conversation from the New chat button', async () => {
    const chat = useChatStore()
    const ui = useUiStore()

    const wrapper = mount(TopNav)
    const button = wrapper.findAll('button').find((b) => b.text().includes('New chat'))
    expect(button).toBeDefined()

    await button!.trigger('click')
    expect(chat.state.conversations).toHaveLength(1)
    expect(ui.state.view).toBe('chat')

    wrapper.unmount()
  })
})

describe('PromptGallery', () => {
  it('renders the curated prompts', () => {
    const wrapper = mount(PromptGallery)
    expect(wrapper.text()).toContain('Ready-to-use programming prompts')
    expect(wrapper.text()).toContain('Explain this code')
    expect(wrapper.text()).toContain('Learn a concept')
  })

  it('filters prompts with the search field', async () => {
    const wrapper = mount(PromptGallery)
    const input = wrapper.get('input[type="search"]')

    await input.setValue('async/await')
    expect(wrapper.text()).toContain('Learn a concept')
    expect(wrapper.text()).not.toContain('Untangle Git history')

    await input.setValue('zzzz-no-match')
    expect(wrapper.text()).toContain('No prompts match')

    wrapper.unmount()
  })

  it('inserts a selected prompt and returns to the chat workspace', async () => {
    const ui = useUiStore()
    ui.setView('documents')

    const wrapper = mount(PromptGallery)
    const card = wrapper.findAll('button').find((button) => button.text().includes('Explain code'))
    expect(card).toBeDefined()

    await card!.trigger('click')
    expect(ui.state.view).toBe('chat')
    expect(ui.state.pendingExample).toBe(PROMPT_CARDS[0]?.prompt)

    wrapper.unmount()
  })
})

describe('DocumentList', () => {
  it('shows an empty state before anything is indexed', () => {
    const wrapper = mount(DocumentList)
    expect(wrapper.text()).toContain('Your knowledge base is empty')
    wrapper.unmount()
  })

  it('filters rows by the search field', async () => {
    const documents = useDocumentsStore()
    documents.mutableState.documents = [
      makeDocument({ doc_id: 'd1', filename: 'gateway.md' }),
      makeDocument({ doc_id: 'd2', filename: 'runbook.txt', extension: '.txt' }),
    ]

    const wrapper = mount(DocumentList)
    expect(wrapper.text()).toContain('gateway.md')
    expect(wrapper.text()).toContain('runbook.txt')

    await wrapper.get('input[type="search"]').setValue('runbook')
    expect(wrapper.text()).toContain('runbook.txt')
    expect(wrapper.text()).not.toContain('gateway.md')

    wrapper.unmount()
  })

  it('requires a second click before deleting, then calls the backend', async () => {
    const documents = useDocumentsStore()
    documents.mutableState.documents = [makeDocument({ doc_id: 'd1' })]

    const remove = vi
      .spyOn(api, 'deleteDocument')
      .mockResolvedValue({ status: 'success', doc_id: 'd1', chunks_removed: 3 })

    const wrapper = mount(DocumentList)
    const button = wrapper.get('[aria-label="Remove gateway.md from the index"]')

    await button.trigger('click')
    expect(button.attributes('title')).toContain('confirm removal')
    expect(remove).not.toHaveBeenCalled()

    await button.trigger('click')
    await vi.waitFor(() => expect(remove).toHaveBeenCalledWith('d1'))

    wrapper.unmount()
  })
})

describe('AppSidebar', () => {
  it('shows a new-chat action and an empty recent list', () => {
    const wrapper = mount(AppSidebar)

    expect(wrapper.text()).toContain('New chat')
    expect(wrapper.text()).toContain('Knowledge base')
    expect(wrapper.text()).toContain('Conversations live in this browser tab only')
    wrapper.unmount()
  })

  it('lists conversations and filters them by search', async () => {
    const chat = useChatStore()
    chat.mutableState.conversations.push(
      makeConversation('c1', 'Fixing the timeout bug'),
      makeConversation('c2', 'Designing a cache layer'),
    )

    const ui = useUiStore()
    const wrapper = mount(AppSidebar)
    expect(wrapper.text()).toContain('Fixing the timeout bug')
    expect(wrapper.text()).toContain('Designing a cache layer')

    const input = wrapper.get('input[type="search"]')
    await input.setValue('timeout')
    expect(wrapper.text()).toContain('Fixing the timeout bug')
    expect(wrapper.text()).not.toContain('Designing a cache layer')

    wrapper.unmount()
    ui.reset()
  })

  it('offers Chat, Documents and Examples in the sidebar navigation', async () => {
    const ui = useUiStore()
    const wrapper = mount(AppSidebar)

    const nav = wrapper.get('nav[aria-label="Workspaces"]')
    const buttons = nav.findAll('button')
    expect(buttons.map((button) => button.text())).toEqual(['Chat', 'Documents', 'Examples'])

    await buttons[2]!.trigger('click')
    expect(ui.state.view).toBe('examples')

    wrapper.unmount()
  })

  it('switches to the documents view from the knowledge-base indicator', async () => {
    const ui = useUiStore()
    const documents = useDocumentsStore()
    documents.mutableState.documents = [makeDocument()]

    const wrapper = mount(AppSidebar)
    const kb = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Knowledge base'))
    expect(kb).toBeDefined()

    await kb!.trigger('click')
    expect(ui.state.view).toBe('documents')
    expect(wrapper.text()).toContain('1 document')

    wrapper.unmount()
  })
})

describe('App shell', () => {
  it('opens on the welcome homepage with the composer ready', () => {
    const wrapper = mount(App)

    expect(wrapper.text()).toContain('AI programming assistant')
    expect(wrapper.text()).toContain('Build, debug, and')
    expect(wrapper.find('textarea#chat-input').exists()).toBe(true)

    wrapper.unmount()
  })

  it('switches between the primary workspaces', async () => {
    const ui = useUiStore()
    const wrapper = mount(App)

    ui.setView('documents')
    await nextTick()
    expect(wrapper.text()).toContain('Your knowledge base')
    expect(wrapper.text()).toContain('Drag & drop files here')

    ui.setView('examples')
    await nextTick()
    expect(wrapper.text()).toContain('Ready-to-use programming prompts')

    wrapper.unmount()
  })
})
