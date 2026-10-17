/**
 * Chat store: conversations, streaming, and the WebSocket lifecycle.
 *
 * Chat history lives in browser memory for the current session only; nothing
 * is persisted to the backend (per the SRS).
 */

import { computed, reactive, readonly } from 'vue'

import { MAX_QUESTION_CHARS, WS_URL } from '@/config'
import { ChatSocketClient } from '@/services/chatSocket'
import type {
  ChatMessage,
  Conversation,
  ServerDoneEvent,
  ServerErrorEvent,
  ServerEvent,
  ServerSourcesEvent,
  ServerStatusEvent,
  ServerTokenEvent,
  SocketStatus,
} from '@/types/chat'
import { titleFromMessage, uid } from '@/utils/format'

type SocketFactory = (url: string, handlers: ConstructorParameters<typeof ChatSocketClient>[1]) => ChatSocketClient

let socketFactory: SocketFactory = (url, handlers) => new ChatSocketClient(url, handlers)

/** Override the socket factory (tests inject a fake client). */
export function setSocketFactory(factory: SocketFactory | null): void {
  socketFactory = factory ?? ((url, handlers) => new ChatSocketClient(url, handlers))
}

interface ChatState {
  conversations: Conversation[]
  activeId: string | null
  isGenerating: boolean
  socketStatus: SocketStatus
  /** Set when a send failed for a reason the user can retry. */
  lastSendError: string | null
  /** Message id currently inspected in the context panel. */
  inspectedMessageId: string | null
}

const state = reactive<ChatState>({
  conversations: [],
  activeId: null,
  isGenerating: false,
  socketStatus: 'idle',
  lastSendError: null,
  inspectedMessageId: null,
})

let socket: ChatSocketClient | null = null
let activeRequestId: string | null = null
let lastFailedQuestion: string | null = null

/* -------------------------------------------------------------------------- */
/* Selectors                                                                   */
/* -------------------------------------------------------------------------- */

const activeConversation = computed<Conversation | null>(
  () => state.conversations.find((conversation) => conversation.id === state.activeId) ?? null,
)

const activeMessages = computed<ChatMessage[]>(() => activeConversation.value?.messages ?? [])

/** Sources of the inspected message, falling back to the latest assistant turn. */
const currentSources = computed(() => {
  const messages = activeMessages.value
  if (!messages.length) return []

  const inspected = state.inspectedMessageId
    ? messages.find((message) => message.id === state.inspectedMessageId)
    : null
  const target =
    inspected ??
    [...messages].reverse().find((message) => message.role === 'assistant' && message.sources) ??
    null

  return target?.sources ?? []
})

/* -------------------------------------------------------------------------- */
/* Internals                                                                   */
/* -------------------------------------------------------------------------- */

function ensureConversation(): Conversation {
  const existing = activeConversation.value
  if (existing) return existing

  const conversation: Conversation = {
    id: uid('conv'),
    title: 'New conversation',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  }
  state.conversations.unshift(conversation)
  state.activeId = conversation.id
  return conversation
}

function findMessage(
  conversation: Conversation | null,
  requestId: string | null,
): ChatMessage | null {
  if (!conversation || !requestId) return null
  return conversation.messages.find((message) => message.id === requestId) ?? null
}

function handleToken(event: ServerTokenEvent): void {
  const conversation = activeConversation.value
  const message = findMessage(conversation, event.request_id)
  if (!message) return
  message.content += event.token
  conversation!.updatedAt = Date.now()
}

function handleSources(event: ServerSourcesEvent): void {
  const conversation = activeConversation.value
  const message = findMessage(conversation, event.request_id)
  if (!message) return
  message.sources = event.sources
  state.inspectedMessageId = message.id
}

function handleStatus(event: ServerStatusEvent): void {
  const conversation = activeConversation.value
  const message = findMessage(conversation, event.request_id)
  if (!message) return
  message.stage = event.stage
}

function handleDone(event: ServerDoneEvent): void {
  const conversation = activeConversation.value
  const message = findMessage(conversation, event.request_id)
  if (message) {
    message.status = 'complete'
    message.stage = undefined
    conversation!.updatedAt = Date.now()
  }
  state.isGenerating = false
  activeRequestId = null
}

function handleError(event: ServerErrorEvent): void {
  const conversation = activeConversation.value
  const message = findMessage(conversation, event.request_id)
  if (message) {
    message.status = 'error'
    message.stage = undefined
    message.error = { code: event.code, message: event.message }
  }
  // Only retry-worthy provider/connection failures keep lastFailedQuestion so
  // "Retry" resends the same question; invalid-input errors do not.
  if (event.code === 'INVALID_MESSAGE' || event.code === 'MESSAGE_TOO_LONG') {
    lastFailedQuestion = null
  }
  state.isGenerating = false
  state.lastSendError = event.message
  activeRequestId = null
}

function onSocketEvent(event: ServerEvent): void {
  switch (event.type) {
    case 'token':
      handleToken(event)
      break
    case 'sources':
      handleSources(event)
      break
    case 'status':
      handleStatus(event)
      break
    case 'done':
      handleDone(event)
      break
    case 'error':
      handleError(event)
      break
  }
}

function onSocketStatus(status: SocketStatus): void {
  state.socketStatus = status
}

function getSocket(): ChatSocketClient {
  if (!socket) {
    socket = socketFactory(WS_URL, { onEvent: onSocketEvent, onStatus: onSocketStatus })
  }
  return socket
}

/* -------------------------------------------------------------------------- */
/* Actions                                                                     */
/* -------------------------------------------------------------------------- */

function newChat(): void {
  state.activeId = null
  state.inspectedMessageId = null
  state.lastSendError = null
  ensureConversation()
}

function selectConversation(id: string): void {
  const conversation = state.conversations.find((item) => item.id === id)
  if (!conversation) return
  state.activeId = id
  state.inspectedMessageId = null
  state.lastSendError = null
}

function clearActiveConversation(): void {
  const conversation = activeConversation.value
  if (!conversation) return
  conversation.messages = []
  conversation.title = 'New conversation'
  conversation.updatedAt = Date.now()
  state.inspectedMessageId = null
  state.lastSendError = null
}

function removeConversation(id: string): void {
  const index = state.conversations.findIndex((item) => item.id === id)
  if (index < 0) return
  const wasActive = state.conversations[index].id === state.activeId
  state.conversations.splice(index, 1)
  if (wasActive) {
    state.activeId = state.conversations[0]?.id ?? null
    state.inspectedMessageId = null
  }
}

function inspectMessage(messageId: string | null): void {
  state.inspectedMessageId = messageId
}

async function sendMessage(content: string): Promise<void> {
  const question = content.trim()
  if (!question || state.isGenerating) return

  if (question.length > MAX_QUESTION_CHARS) {
    state.lastSendError = `Your message is too long (${question.length.toLocaleString()} characters). Please keep it under ${MAX_QUESTION_CHARS.toLocaleString()} characters.`
    return
  }

  const conversation = ensureConversation()
  const requestId = uid('msg')

  const userMessage: ChatMessage = {
    id: uid('user'),
    role: 'user',
    content: question,
    createdAt: Date.now(),
    status: 'complete',
  }
  const assistantMessage: ChatMessage = {
    id: requestId,
    role: 'assistant',
    content: '',
    createdAt: Date.now(),
    status: 'streaming',
  }

  if (conversation.messages.length === 0) {
    conversation.title = titleFromMessage(question)
  }
  conversation.messages.push(userMessage, assistantMessage)
  conversation.updatedAt = Date.now()

  state.isGenerating = true
  state.lastSendError = null
  state.inspectedMessageId = null
  activeRequestId = requestId
  lastFailedQuestion = question

  try {
    await getSocket().send({ type: 'message', request_id: requestId, message: question })
  } catch {
    assistantMessage.status = 'error'
    assistantMessage.error = {
      code: 'CONNECTION_FAILED',
      message:
        'Could not connect to the backend. Check that the server is running, then retry.',
    }
    state.isGenerating = false
    state.lastSendError = 'Connection failed'
    activeRequestId = null
  }
}

function stopGeneration(): void {
  if (!state.isGenerating || !activeRequestId) return
  getSocket().cancel(activeRequestId)

  const conversation = activeConversation.value
  const message = findMessage(conversation, activeRequestId)
  if (message && message.status === 'streaming') {
    message.status = 'stopped'
    message.stage = undefined
    if (!message.content) {
      message.content = '_Generation stopped._'
    }
  }
  state.isGenerating = false
  activeRequestId = null
}

/** Re-send the question whose answer failed. */
async function retryLast(): Promise<void> {
  const conversation = activeConversation.value
  if (!conversation || state.isGenerating) return

  const lastUser = [...conversation.messages].reverse().find((message) => message.role === 'user')
  const question = lastFailedQuestion ?? lastUser?.content
  if (!question) return

  // Drop the failed assistant turn (and the user turn we are re-sending).
  const lastAssistant = conversation.messages[conversation.messages.length - 1]
  if (lastAssistant?.role === 'assistant' && lastAssistant.error) {
    conversation.messages.pop()
  }
  const lastUserMessage = conversation.messages[conversation.messages.length - 1]
  if (lastUserMessage?.role === 'user' && lastUserMessage.content === question) {
    conversation.messages.pop()
  }
  state.lastSendError = null
  await sendMessage(question)
}

function reset(): void {
  state.conversations = []
  state.activeId = null
  state.isGenerating = false
  state.socketStatus = 'idle'
  state.lastSendError = null
  state.inspectedMessageId = null
  activeRequestId = null
  lastFailedQuestion = null
  socket?.close()
  socket = null
}

export function useChatStore() {
  return {
    state: readonly(state),
    get mutableState() {
      return state
    },
    activeConversation,
    activeMessages,
    currentSources,
    newChat,
    selectConversation,
    clearActiveConversation,
    removeConversation,
    inspectMessage,
    sendMessage,
    stopGeneration,
    retryLast,
    reset,
    /** Exposed for component-level tests. */
    onSocketEvent,
  }
}
