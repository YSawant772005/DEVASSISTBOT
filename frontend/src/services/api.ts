/**
 * HTTP service layer.
 *
 * All backend calls go through this module; components never build URLs
 * themselves. Errors are normalised into :class:`ApiError` so callers can show
 * a friendly message without parsing FastAPI payloads.
 */

import { API_BASE_URL, ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_LABEL } from '@/config'
import type {
  DeleteResponse,
  DocumentListResponse,
  HealthResponse,
  UploadResponse,
} from '@/types/chat'
import { formatBytes } from '@/utils/format'

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

interface BackendErrorBody {
  status?: string
  code?: string
  message?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
    })
  } catch {
    throw new ApiError(
      'NETWORK_ERROR',
      'Could not reach the DevAssist backend. Make sure it is running on ' +
        `${API_BASE_URL} and try again.`,
    )
  }

  if (!response.ok) {
    let body: BackendErrorBody = {}
    try {
      body = (await response.json()) as BackendErrorBody
    } catch {
      // Non-JSON error body (proxy/HTML) — fall through to a generic message.
    }
    throw new ApiError(
      body.code || 'HTTP_ERROR',
      body.message || `Request failed with status ${response.status}.`,
      response.status,
    )
  }

  return (await response.json()) as T
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}

export function fetchDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/documents')
}

export function deleteDocument(docId: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
}

export function clearDocuments(): Promise<DeleteResponse> {
  return request<DeleteResponse>('/documents', { method: 'DELETE' })
}

/** Result of a client-side pre-check (the server re-validates everything). */
export type FileValidation = { ok: true } | { ok: false; message: string }

export function validateFile(file: File): FileValidation {
  const lower = file.name.toLowerCase()
  const allowed = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))
  if (!allowed) {
    return {
      ok: false,
      message: `"${file.name}" is not a supported file type. Use PDF, TXT or MD.`,
    }
  }
  if (file.size === 0) {
    return { ok: false, message: `"${file.name}" is empty.` }
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      message: `"${file.name}" is ${formatBytes(file.size)}. Uploads must be under ${MAX_UPLOAD_LABEL}.`,
    }
  }
  return { ok: true }
}

/**
 * Upload a file via XMLHttpRequest so real progress events are available
 * (fetch cannot report upload progress).
 */
export function uploadDocument(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise<UploadResponse>((resolve, reject) => {
    const form = new FormData()
    form.append('file', file, file.name)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE_URL}/upload`)
    xhr.responseType = 'text'

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)))
      }
    }

    xhr.onerror = () => {
      reject(
        new ApiError(
          'NETWORK_ERROR',
          `Could not reach the backend at ${API_BASE_URL}. Is it running?`,
        ),
      )
    }

    xhr.ontimeout = () => reject(new ApiError('TIMEOUT', 'The upload timed out. Please try again.'))

    xhr.onload = () => {
      let body: UploadResponse | BackendErrorBody = {}
      try {
        body = JSON.parse(xhr.responseText) as UploadResponse & BackendErrorBody
      } catch {
        reject(new ApiError('BAD_RESPONSE', 'The backend returned an unexpected response.'))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300 && (body as UploadResponse).status === 'success') {
        if (onProgress) onProgress(100)
        resolve(body as UploadResponse)
      } else {
        const errorBody = body as BackendErrorBody
        reject(
          new ApiError(
            errorBody.code || 'UPLOAD_FAILED',
            errorBody.message || `Upload failed with status ${xhr.status}.`,
            xhr.status,
          ),
        )
      }
    }

    xhr.send(form)
  })
}
