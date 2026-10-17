/** Shared frontend types mirroring the backend API and WebSocket contract. */

export type Role = 'user' | 'assistant'

export type MessageStatus = 'streaming' | 'complete' | 'error' | 'stopped'

export interface SourceReference {
  doc_id: string
  filename: string
  chunk_index: number
  /** Cosine similarity reported by the FAISS index (0–1). */
  score: number
  preview: string
}

export interface ChatMessage {
  id: string
  role: Role
  content: string
  createdAt: number
  status: MessageStatus
  sources?: SourceReference[]
  error?: { code: string; message: string }
  /** Set while the backend is retrieving/generating. */
  stage?: string
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
}

export interface UploadedDocument {
  doc_id: string
  filename: string
  extension: string
  size_bytes: number
  chunks: number
  uploaded_at: string
}

export interface DocumentListResponse {
  documents: UploadedDocument[]
  total_documents: number
  total_chunks: number
}

export interface DeleteResponse {
  status: 'success'
  doc_id: string | null
  chunks_removed: number
}

export interface UploadResponse {
  status: 'success'
  doc_id: string
  filename: string
  extension: string
  size_bytes: number
  chunks_processed: number
  characters_extracted: number
}

export interface HealthLimits {
  max_upload_bytes: number
  chunk_size: number
  chunk_overlap: number
  top_k: number
  max_context_tokens: number
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  model: string
  groq_configured: boolean
  embedding_model: string
  embedding_loaded: boolean
  documents_indexed: number
  chunks_indexed: number
  limits: HealthLimits
  warnings: string[]
}

export type UploadState = 'uploading' | 'processing' | 'indexed' | 'failed'

export interface UploadJob {
  id: string
  filename: string
  sizeBytes: number
  state: UploadState
  progress: number
  chunks?: number
  message?: string
}

export type SocketStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

export type ConnectionState = 'unknown' | 'online' | 'degraded' | 'offline'

/* --- WebSocket events (server -> client) --------------------------------- */

export interface ServerStatusEvent {
  type: 'status'
  request_id: string
  stage: string
}

export interface ServerSourcesEvent {
  type: 'sources'
  request_id: string
  sources: SourceReference[]
}

export interface ServerTokenEvent {
  type: 'token'
  request_id: string
  token: string
}

export interface ServerDoneEvent {
  type: 'done'
  request_id: string
}

export interface ServerErrorEvent {
  type: 'error'
  request_id: string
  code: string
  message: string
}

export type ServerEvent =
  | ServerStatusEvent
  | ServerSourcesEvent
  | ServerTokenEvent
  | ServerDoneEvent
  | ServerErrorEvent

/* --- WebSocket messages (client -> server) ------------------------------- */

export interface ClientMessageEvent {
  type: 'message'
  request_id: string
  message: string
}

export interface ClientCancelEvent {
  type: 'cancel'
  request_id: string
}

export type ClientEvent = ClientMessageEvent | ClientCancelEvent
