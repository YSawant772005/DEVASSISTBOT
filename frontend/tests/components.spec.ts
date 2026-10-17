import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ChatComposer from '@/components/ChatComposer.vue'
import MarkdownMessage from '@/components/MarkdownMessage.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import WelcomeState from '@/components/WelcomeState.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import type { ChatMessage } from '@/types/chat'

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'm1',
    role: 'assistant',
    content: 'Use `git rebase` to replay commits.',
    createdAt: Date.now(),
    status: 'complete',
    ...overrides,
  }
}

describe('ChatComposer', () => {
  it('sends on Enter and clears the draft', async () => {
    const wrapper = mount(ChatComposer, { props: { isGenerating: false } })
    const textarea = wrapper.find('textarea')

    await textarea.setValue('Explain closures')
    await textarea.trigger('keydown', { key: 'Enter' })

    const events = wrapper.emitted('send')
    expect(events).toHaveLength(1)
    expect(events?.[0]).toEqual(['Explain closures'])
    expect((textarea.element as HTMLTextAreaElement).value).toBe('')
  })

  it('does not send on Shift+Enter (newline instead)', async () => {
    const wrapper = mount(ChatComposer, { props: { isGenerating: false } })
    const textarea = wrapper.find('textarea')

    await textarea.setValue('line one')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })

    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('replaces send with stop while generating', async () => {
    const wrapper = mount(ChatComposer, { props: { isGenerating: true } })
    await wrapper.find('textarea').setValue('Hello')

    // Send is not rendered at all, so a generation cannot be superseded.
    expect(wrapper.find('[aria-label="Send message"]').exists()).toBe(false)
    await wrapper.find('[aria-label="Stop generating"]').trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('does not send when the draft is empty', async () => {
    const wrapper = mount(ChatComposer, { props: { isGenerating: false } })
    await wrapper.find('[aria-label="Send message"]').trigger('click')
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('shows a counter and blocks send beyond the limit', async () => {
    const wrapper = mount(ChatComposer, { props: { isGenerating: false } })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('x'.repeat(4100))
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.text()).toContain('4,100')
  })
})

describe('MessageBubble', () => {
  it('renders assistant markdown content', () => {
    const wrapper = mount(MessageBubble, { props: { message: makeMessage() } })
    expect(wrapper.find('.md-body').exists()).toBe(true)
    expect(wrapper.text()).toContain('git rebase')
  })

  it('renders user messages as plain pre-wrapped text', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: makeMessage({ role: 'user', content: '# not a heading' }) },
    })
    expect(wrapper.find('pre').text()).toBe('# not a heading')
    expect(wrapper.find('.md-body').exists()).toBe(false)
  })

  it('emits retry when the message failed', async () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: makeMessage({
          status: 'error',
          error: { code: 'RATE_LIMITED', message: 'Traffic is high. Please wait 10 seconds before asking again.' },
        }),
      },
    })

    expect(wrapper.find('[role="alert"]').text()).toContain('Traffic is high')
    await wrapper.find('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('renders source chips with filename, chunk and score', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: makeMessage({
          sources: [{ doc_id: 'd1', filename: 'gateway.md', chunk_index: 2, score: 0.81, preview: 'text' }],
        }),
      },
    })

    expect(wrapper.text()).toContain('gateway.md')
    expect(wrapper.text()).toContain('ch 3')
    expect(wrapper.text()).toContain('81%')
  })

  it('shows a streaming placeholder and caret before the first token', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: makeMessage({ content: '', status: 'streaming', stage: 'retrieving' }) },
    })
    expect(wrapper.text()).toContain('Searching your documents…')
  })
})

describe('MarkdownMessage', () => {
  it('copies code block content to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mount(MarkdownMessage, {
      props: { content: '```python\nprint("hi")\n```' },
    })

    const button = wrapper.find('[data-copy-code]')
    expect(button.exists()).toBe(true)
    expect(button.text()).toBe('Copy')

    await button.trigger('click')
    await flushPromises()

    // The fence keeps its trailing newline; compare on trimmed content.
    expect(writeText).toHaveBeenCalledTimes(1)
    expect(writeText.mock.calls[0]?.[0]?.trim()).toBe('print("hi")')
    expect(button.text()).toBe('Copied!')
  })
})

describe('WelcomeState', () => {
  afterEach(() => {
    useDocumentsStore().reset()
    useChatStore().reset()
  })

  it('emits the prompt for the Explain code quick-start card', async () => {
    const wrapper = mount(WelcomeState)
    const buttons = wrapper
      .findAll('button')
      .filter((button) => button.text().includes('Explain code'))
    expect(buttons).toHaveLength(1)

    await buttons[0]!.trigger('click')
    const emitted = wrapper.emitted('select')
    expect(emitted).toHaveLength(1)
    expect(typeof emitted?.[0]?.[0]).toBe('string')
    expect(emitted?.[0]?.[0]).toBe('Explain what this function does and why.')
  })

  it('renders the four quick-start cards with titles and descriptions', () => {
    const wrapper = mount(WelcomeState)
    const cards = wrapper.findAll('button').filter((button) => button.classes().includes('prompt-card'))

    expect(cards).toHaveLength(4)
    for (const title of ['Explain code', 'Debug an error', 'Ask my documents', 'Learn a concept']) {
      expect(wrapper.text()).toContain(title)
    }
    expect(wrapper.text()).toContain('Build, debug, and')
    expect(wrapper.text()).toContain('AI programming assistant')
  })

  it('shows the no-documents hint when nothing is indexed', () => {
    const wrapper = mount(WelcomeState)
    expect(wrapper.text()).toContain('No documents indexed yet')
    expect(wrapper.text()).toContain('Upload documents')
  })

  it('reports the real indexed document count once documents exist', () => {
    const documents = useDocumentsStore()
    documents.mutableState.documents = [
      {
        doc_id: 'd1',
        filename: 'gateway.md',
        extension: '.md',
        size_bytes: 2048,
        chunks: 3,
        uploaded_at: new Date().toISOString(),
      },
    ]

    const wrapper = mount(WelcomeState)
    expect(wrapper.text()).toContain('1 document ready')
    expect(wrapper.text()).not.toContain('No documents indexed yet')
  })
})
