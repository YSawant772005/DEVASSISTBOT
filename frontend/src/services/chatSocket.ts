/**
 * WebSocket client for the ``/ws/chat`` streaming protocol.
 *
 * The connection is created lazily on the first message and kept open. If it
 * drops, the next send reconnects automatically. The backend allows one
 * in-flight generation per connection; :meth:`cancel` stops it server-side.
 */

import type { ClientEvent, ServerEvent, SocketStatus } from '@/types/chat'

export interface ChatSocketHandlers {
  onEvent: (event: ServerEvent) => void
  onStatus?: (status: SocketStatus, detail?: string) => void
}

export class ChatSocketClient {
  private socket: WebSocket | null = null
  private queue: string[] = []
  private readonly url: string
  private readonly handlers: ChatSocketHandlers

  constructor(url: string, handlers: ChatSocketHandlers) {
    this.url = url
    this.handlers = handlers
  }

  get status(): SocketStatus {
    if (!this.socket) return 'idle'
    if (this.socket.readyState === WebSocket.OPEN) return 'open'
    if (this.socket.readyState === WebSocket.CONNECTING) return 'connecting'
    return 'closed'
  }

  /** Open the socket if needed and wait until it is ready to send. */
  connect(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }
    if (this.socket?.readyState === WebSocket.CONNECTING) {
      return new Promise((resolve, reject) => {
        this.socket!.addEventListener('open', () => resolve(), { once: true })
        this.socket!.addEventListener(
          'error',
          () => reject(new Error('WebSocket connection failed')),
          { once: true },
        )
      })
    }

    return new Promise((resolve, reject) => {
      let settled = false
      this.setStatus('connecting')

      const socket = new WebSocket(this.url)
      this.socket = socket

      socket.onopen = () => {
        settled = true
        this.setStatus('open')
        this.flushQueue()
        resolve()
      }

      socket.onmessage = (message) => {
        try {
          this.handlers.onEvent(JSON.parse(message.data as string) as ServerEvent)
        } catch {
          // Ignore frames that are not valid JSON; the protocol guarantees they are.
        }
      }

      socket.onerror = () => {
        if (!settled) {
          settled = true
          this.setStatus('error', 'connection failed')
          reject(new Error('WebSocket connection failed'))
        } else {
          this.setStatus('error')
        }
      }

      socket.onclose = () => {
        this.socket = null
        this.setStatus('closed')
        if (!settled) {
          settled = true
          reject(new Error('WebSocket closed before opening'))
        }
      }
    })
  }

  /** Send a client event, connecting first if necessary. */
  async send(event: ClientEvent): Promise<void> {
    await this.connect()
    const payload = JSON.stringify(event)
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(payload)
    } else {
      // Rare race: the socket closed while we awaited connect().
      this.queue.push(payload)
      await this.connect()
    }
  }

  cancel(requestId: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'cancel', request_id: requestId } satisfies ClientEvent))
    }
  }

  close(): void {
    this.queue = []
    if (this.socket) {
      this.socket.onclose = null
      this.socket.close()
      this.socket = null
      this.setStatus('closed')
    }
  }

  private flushQueue(): void {
    while (this.queue.length && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(this.queue.shift() as string)
    }
  }

  private setStatus(status: SocketStatus, detail?: string): void {
    this.handlers.onStatus?.(status, detail)
  }
}
