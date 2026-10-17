<script setup lang="ts">
/**
 * Settings dialog: live backend diagnostics read from GET /health.
 * Contains no secrets — the Groq key stays on the backend.
 */
import { computed, onMounted, ref } from 'vue'
import { CheckCircle2, ExternalLink, Moon, RefreshCw, Sun, X } from 'lucide-vue-next'

import { API_BASE_URL, WS_URL } from '@/config'
import { useDocumentsStore } from '@/stores/documents'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits<{ close: [] }>()

const documents = useDocumentsStore()
const ui = useUiStore()

const checking = ref(false)

const health = computed(() => documents.state.health)

onMounted(() => {
  void refresh()
})

async function refresh(): Promise<void> {
  checking.value = true
  await documents.checkHealth()
  checking.value = false
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-labelledby="settings-title"
    @keydown="onKeydown"
    @click.self="emit('close')"
  >
    <div class="panel animate-fade-up w-full max-w-md p-5 shadow-2xl">
      <header class="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 id="settings-title" class="text-base font-semibold text-ink">Settings</h2>
          <p class="text-xs text-muted">Local DevAssist configuration and status.</p>
        </div>
        <button type="button" class="icon-btn" aria-label="Close settings" @click="emit('close')">
          <X class="h-4 w-4" />
        </button>
      </header>

      <dl class="space-y-2.5 text-xs">
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">Backend URL</dt>
          <dd class="flex items-center gap-1 font-mono text-[0.7rem] text-ink">
            {{ API_BASE_URL }}
          </dd>
        </div>
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">WebSocket</dt>
          <dd class="truncate font-mono text-[0.7rem] text-ink" :title="WS_URL">{{ WS_URL }}</dd>
        </div>
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">Groq model</dt>
          <dd class="truncate font-mono text-[0.7rem] text-ink" :title="health?.model">
            {{ health?.model ?? '—' }}
          </dd>
        </div>
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">Embedding model</dt>
          <dd class="truncate font-mono text-[0.7rem] text-ink" :title="health?.embedding_model">
            {{ health?.embedding_model ?? '—' }}
          </dd>
        </div>
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">Retrieval</dt>
          <dd class="text-[0.7rem] text-ink">
            <template v-if="health">
              top {{ health.limits.top_k }} · {{ health.limits.chunk_size }} char chunks ·
              {{ health.limits.chunk_overlap }} overlap
            </template>
            <template v-else>—</template>
          </dd>
        </div>
        <div class="flex items-start justify-between gap-3">
          <dt class="text-muted">Upload limit</dt>
          <dd class="text-[0.7rem] text-ink">
            {{ health ? `${Math.round(health.limits.max_upload_bytes / 1024 / 1024)} MB` : '—' }}
          </dd>
        </div>
      </dl>

      <div class="mt-4 rounded-lg border border-line bg-surface-2 px-3 py-2.5">
        <p class="flex items-center gap-2 text-xs">
          <CheckCircle2
            v-if="health?.groq_configured"
            class="h-3.5 w-3.5 text-ok"
            aria-hidden="true"
          />
          <span :class="health?.groq_configured ? 'text-ink' : 'text-warn'">
            {{ health?.groq_configured ? 'Groq credentials configured' : 'Groq credentials missing' }}
          </span>
        </p>
        <p v-if="!health?.groq_configured" class="mt-1.5 text-[0.7rem] leading-relaxed text-muted">
          Add <code class="rounded bg-surface-3 px-1 py-0.5 font-mono">GROQ_API_KEY</code> to
          <code class="rounded bg-surface-3 px-1 py-0.5 font-mono">backend/.env</code> and restart
          the backend. The key is never sent to the browser.
        </p>
      </div>

      <ul v-if="health?.warnings.length" class="mt-2 space-y-1.5">
        <li
          v-for="warning in health.warnings"
          :key="warning"
          class="rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-[0.7rem] leading-relaxed text-warn"
        >
          {{ warning }}
        </li>
      </ul>

      <p class="mt-3 text-[0.65rem] leading-relaxed text-faint">
        Documents and chat live in memory only: restarting the backend clears the index and
        refreshing this page clears the conversation.
      </p>

      <footer class="mt-4 flex items-center gap-2 border-t border-line pt-3">
        <button type="button" class="btn btn-soft" :disabled="checking" @click="refresh">
          <RefreshCw class="h-3.5 w-3.5" :class="checking ? 'animate-spin' : ''" aria-hidden="true" />
          {{ checking ? 'Checking…' : 'Test connection' }}
        </button>
        <button type="button" class="btn btn-soft" @click="ui.toggleTheme()">
          <Sun v-if="ui.state.theme === 'dark'" class="h-3.5 w-3.5" aria-hidden="true" />
          <Moon v-else class="h-3.5 w-3.5" aria-hidden="true" />
          Theme
        </button>
        <a
          class="btn btn-ghost ml-auto"
          :href="`${API_BASE_URL}/docs`"
          target="_blank"
          rel="noopener noreferrer"
        >
          API docs
          <ExternalLink class="h-3 w-3" aria-hidden="true" />
        </a>
      </footer>
    </div>
  </div>
</template>
