/** Lightweight reactive store using Vue's reactivity (no extra dependencies). */

import { reactive, readonly } from 'vue'

import * as api from '@/services/api'
import type { ConnectionState, HealthResponse, UploadJob, UploadedDocument } from '@/types/chat'
import { uid } from '@/utils/format'

interface DocumentsState {
  documents: UploadedDocument[]
  totalChunks: number
  jobs: UploadJob[]
  loading: boolean
  error: string | null
  health: HealthResponse | null
  connection: ConnectionState
}

const state = reactive<DocumentsState>({
  documents: [],
  totalChunks: 0,
  jobs: [],
  loading: false,
  error: null,
  health: null,
  connection: 'unknown',
})

async function refresh(): Promise<void> {
  state.loading = true
  try {
    const response = await api.fetchDocuments()
    state.documents = response.documents
    state.totalChunks = response.total_chunks
    state.error = null
  } catch (error) {
    state.error = error instanceof api.ApiError ? error.message : 'Could not load documents.'
  } finally {
    state.loading = false
  }
}

async function checkHealth(): Promise<void> {
  try {
    const health = await api.fetchHealth()
    state.health = health
    state.connection = health.status === 'ok' ? 'online' : 'degraded'
  } catch {
    state.health = null
    state.connection = 'offline'
  }
}

function dismissJob(jobId: string): void {
  const index = state.jobs.findIndex((job) => job.id === jobId)
  if (index >= 0) state.jobs.splice(index, 1)
}

/** Upload a batch of files, reporting real progress and backend results. */
async function uploadFiles(files: File[]): Promise<void> {
  for (const file of files) {
    const validation = api.validateFile(file)
    if (!validation.ok) {
      state.jobs.unshift({
        id: uid('job'),
        filename: file.name,
        sizeBytes: file.size,
        state: 'failed',
        progress: 0,
        message: validation.message,
      })
      continue
    }

    const job: UploadJob = {
      id: uid('job'),
      filename: file.name,
      sizeBytes: file.size,
      state: 'uploading',
      progress: 0,
    }
    state.jobs.unshift(job)

    try {
      const response = await api.uploadDocument(file, (percent) => {
        job.progress = percent
        if (percent >= 99) job.state = 'processing'
      })
      job.state = 'indexed'
      job.chunks = response.chunks_processed
      await refresh()
    } catch (error) {
      job.state = 'failed'
      job.message =
        error instanceof api.ApiError ? error.message : 'Upload failed for an unknown reason.'
    }
  }
}

async function removeDocument(docId: string): Promise<void> {
  try {
    await api.deleteDocument(docId)
    const index = state.documents.findIndex((doc) => doc.doc_id === docId)
    if (index >= 0) {
      state.totalChunks = Math.max(0, state.totalChunks - (state.documents[index]?.chunks ?? 0))
      state.documents.splice(index, 1)
    }
    state.error = null
  } catch (error) {
    state.error = error instanceof api.ApiError ? error.message : 'Could not remove the document.'
  }
}

async function clearAll(): Promise<void> {
  try {
    await api.clearDocuments()
    state.documents = []
    state.totalChunks = 0
    state.error = null
  } catch (error) {
    state.error = error instanceof api.ApiError ? error.message : 'Could not clear documents.'
  }
}

/** Replace state (used by tests). */
function reset(): void {
  state.documents = []
  state.totalChunks = 0
  state.jobs = []
  state.loading = false
  state.error = null
  state.health = null
  state.connection = 'unknown'
}

export function useDocumentsStore() {
  return {
    state: readonly(state),
    get mutableState() {
      return state
    },
    refresh,
    checkHealth,
    uploadFiles,
    removeDocument,
    clearAll,
    dismissJob,
    reset,
  }
}
