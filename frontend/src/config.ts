/**
 * Runtime configuration for the DevAssist frontend.
 *
 * Only public, non-secret values live here. The Groq API key is never part of
 * the frontend bundle: all model calls happen on the backend.
 */

const rawApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()

export const API_BASE_URL = (rawApiBase || 'http://localhost:8000').replace(/\/+$/, '')

const rawWsUrl = (import.meta.env.VITE_WS_URL as string | undefined)?.trim()

export const WS_URL =
  rawWsUrl || `${API_BASE_URL.replace(/^http/, 'ws')}/ws/chat`

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
export const MAX_UPLOAD_LABEL = '5 MB'

export const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.markdown'] as const
export const ALLOWED_EXTENSIONS_LABEL = 'PDF, TXT, MD'

/** Maximum question length enforced by the backend (`MAX_QUESTION_CHARS`). */
export const MAX_QUESTION_CHARS = 4000

/** Static, clearly-labelled starter prompts for the contextual panel. */
export const FOLLOW_UP_SUGGESTIONS: string[] = [
  'What are the trade-offs of this approach?',
  'Show a minimal test for that code.',
  'How would this scale to 10x traffic?',
  'Rewrite that example with better error handling.',
]
