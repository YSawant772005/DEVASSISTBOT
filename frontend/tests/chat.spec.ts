import { beforeEach, describe, expect, it } from 'vitest'

import { setSocketFactory, useChatStore } from '@/stores/chat'
import type { ClientEvent, ServerEvent } from '@/types/chat'

/** Minimal stand-in for ChatSocketClient that records outbound events. */
class FakeSocket {
  sent: ClientEvent[] = []
  cancelled: string[] = []
  closed = false

  async send(event: ClientEvent): Promise<void> {
    this.sent.push(event)
  }

  cancel(requestId: string): void {
    this.cancelled.push(requestId)
  }

  close(): void {
    this.closed = true
  }

  get lastMessage(): ClientEvent & { type: 'message' } {
    const event = [...this.sent].reverse().find((item) => item.type === 'message')
    if (!event || event.type !== 'message') throw new Error('no message sent')
    return event
  }
}

let socket: FakeSocket

function emit(event: Omit<ServerEvent, 'request_id'> & { request_id?: string }): void {
  useChatStore().onSocketEvent({
    ...event,
    request_id: event.request_id ?? socket.lastMessage.request_id,
  } as ServerEvent)
}

async function sendAndCapture(question: string): Promise<string> {
  await useChatStore().sendMessage(question)
  return socket.lastMessage.request_id
}

beforeEach(() => {
  socket = new FakeSocket()
  setSocketFactory(() => socket as never)
  useChatStore().reset()
})

describe('chat store', () => {
  it('starts with no conversation and no messages', () => {
    const chat = useChatStore()
    expect(chat.state.conversations).toHaveLength(0)
    expect(chat.activeMessages.value).toHaveLength(0)
    expect(chat.state.isGenerating).toBe(false)
  })

  it('sends a question and creates user + streaming assistant messages', async () => {
    const chat = useChatStore()
    await chat.sendMessage('How do I fix a TypeError?')

    expect(socket.sent).toHaveLength(1)
    expect(socket.lastMessage.message).toBe('How do I fix a TypeError?')
    expect(chat.state.isGenerating).toBe(true)
    expect(chat.activeMessages.value).toHaveLength(2)
    expect(chat.activeMessages.value[0]?.role).toBe('user')
    expect(chat.activeMessages.value[1]?.role).toBe('assistant')
    expect(chat.activeMessages.value[1]?.content).toBe('')
    expect(chat.activeConversation.value?.title).toContain('TypeError')
  })

  it('ignores empty and whitespace-only messages', async () => {
    const chat = useChatStore()
    await chat.sendMessage('   ')
    expect(socket.sent).toHaveLength(0)
    expect(chat.state.conversations).toHaveLength(0)
  })

  it('appends streamed tokens to one assistant message', async () => {
    const chat = useChatStore()
    const requestId = await sendAndCapture('Explain closures')

    emit({ type: 'status', stage: 'retrieving' })
    emit({ type: 'token', token: 'Check ' })
    emit({ type: 'token', token: 'the traceback.' })
    emit({ type: 'done' })

    const assistant = chat.activeMessages.value[1]
    expect(assistant?.content).toBe('Check the traceback.')
    expect(assistant?.status).toBe('complete')
    expect(chat.state.isGenerating).toBe(false)
    expect(requestId).toBeTruthy()
  })

  it('records sources and exposes them for the context panel', async () => {
    const chat = useChatStore()
    await sendAndCapture('What is the retry policy?')

    emit({
      type: 'sources',
      sources: [
        {
          doc_id: 'd1',
          filename: 'gateway.md',
          chunk_index: 2,
          score: 0.8123,
          preview: 'The gateway retries three times.',
        },
      ],
    })

    const assistant = chat.activeMessages.value[1]
    expect(assistant?.sources).toHaveLength(1)
    expect(chat.currentSources.value[0]?.filename).toBe('gateway.md')
    // The source panel now points at the message that carried them.
    expect(chat.state.inspectedMessageId).toBe(assistant?.id)
  })

  it('surfaces error events with the backend message and enables retry', async () => {
    const chat = useChatStore()
    await sendAndCapture('Explain decorators')

    emit({ type: 'error', code: 'RATE_LIMITED', message: 'Traffic is high. Please wait 10 seconds before asking again.' })

    const assistant = chat.activeMessages.value[1]
    expect(assistant?.status).toBe('error')
    expect(assistant?.error?.code).toBe('RATE_LIMITED')
    expect(assistant?.error?.message).toContain('Traffic is high')
    expect(chat.state.isGenerating).toBe(false)
    expect(chat.state.lastSendError).toContain('Traffic is high')
  })

  it('stops generation locally and cancels server-side', async () => {
    const chat = useChatStore()
    const requestId = await sendAndCapture('Long answer please')

    emit({ type: 'token', token: 'Partial' })
    chat.stopGeneration()

    expect(socket.cancelled).toEqual([requestId])
    expect(chat.state.isGenerating).toBe(false)
    expect(chat.activeMessages.value[1]?.status).toBe('stopped')
    expect(chat.activeMessages.value[1]?.content).toBe('Partial')
  })

  it('refuses a second message while one is generating', async () => {
    const chat = useChatStore()
    await chat.sendMessage('First question')
    await chat.sendMessage('Second question')

    expect(socket.sent).toHaveLength(1)
    expect(chat.activeMessages.value).toHaveLength(2)
  })

  it('rejects messages above the configured limit', async () => {
    const chat = useChatStore()
    await chat.sendMessage('x'.repeat(5000))

    expect(socket.sent).toHaveLength(0)
    expect(chat.state.lastSendError).toContain('4,000')
  })

  it('marks the message as failed when the socket send rejects', async () => {
    setSocketFactory(
      () =>
        ({
          async send(): Promise<void> {
            throw new Error('connection refused')
          },
          cancel(): void {},
          close(): void {},
        }) as never,
    )

    const chat = useChatStore()
    await chat.sendMessage('Anything')

    const assistant = chat.activeMessages.value[1]
    expect(assistant?.status).toBe('error')
    expect(assistant?.error?.code).toBe('CONNECTION_FAILED')
    expect(chat.state.isGenerating).toBe(false)
  })

  it('keeps separate conversations and switches between them', async () => {
    const chat = useChatStore()
    await chat.sendMessage('First chat question')
    const firstId = chat.state.activeId

    chat.newChat()
    await chat.sendMessage('Second chat question')

    expect(chat.state.conversations).toHaveLength(2)
    expect(chat.state.activeId).not.toBe(firstId)

    chat.selectConversation(firstId as string)
    expect(chat.activeMessages.value[0]?.content).toBe('First chat question')
    expect(chat.activeConversation.value?.title).toBe('First chat question')
  })

  it('clears the active conversation without deleting others', async () => {
    const chat = useChatStore()
    await chat.sendMessage('Question A')
    const firstId = chat.state.activeId
    chat.newChat()
    await chat.sendMessage('Question B')

    chat.selectConversation(firstId as string)
    chat.clearActiveConversation()

    expect(chat.activeMessages.value).toHaveLength(0)
    expect(chat.state.conversations).toHaveLength(2)
  })

  it('removes a conversation', async () => {
    const chat = useChatStore()
    await chat.sendMessage('Doomed conversation')

    chat.removeConversation(chat.state.activeId as string)

    expect(chat.state.conversations).toHaveLength(0)
    expect(chat.activeConversation.value).toBeNull()
  })

  it('shows general-knowledge state when a message has no sources', async () => {
    const chat = useChatStore()
    await sendAndCapture('What is a closure?')
    emit({ type: 'token', token: 'A closure…' })
    emit({ type: 'done' })

    expect(chat.currentSources.value).toHaveLength(0)
  })
})
