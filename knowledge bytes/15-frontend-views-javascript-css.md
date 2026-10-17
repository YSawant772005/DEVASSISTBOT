# 15 — Frontend Views, JavaScript, and CSS

**Overview:** The frontend is a Vue 3 single-page app written in TypeScript with `<script setup>` components, built by Vite and styled with Tailwind CSS v4. There is no router, no Pinia/Vuex, and no CSS framework config file — view switching is a store flag, state is plain Vue reactivity, and the theme is one stylesheet of CSS custom properties. This document walks the shell, the three views, the interaction logic, and the styling system.

**Scope:** App shell and responsive layout, view switching, component responsibilities, composables, styling/theming, and frontend–backend communication. Testing is covered separately in [18 — Testing and verification](18-testing-and-verification.md).

**Prerequisites:** [00 — Project architecture](00-project-architecture.md), Byte 5; [04 — Models and ViewModels](04-models-and-viewmodels.md).

**Important source files:**
- `frontend/src/App.vue`
- `frontend/src/stores/ui.ts`
- `frontend/src/components/` (all)
- `frontend/src/style.css`, `frontend/src/main.ts`
- `frontend/src/services/api.ts`, `frontend/src/services/chatSocket.ts`

---

### Byte 1: The shell — App.vue and responsive layout

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 5

**Source files:** `frontend/src/App.vue`, `frontend/src/composables/useMediaQuery.ts`

**In plain terms:**

`App.vue` assembles four regions — top nav, collapsible left sidebar, the active workspace, and an optional right context panel — and converts the side panels into overlay drawers on smaller screens.

**The code:**

```typescript
// frontend/src/App.vue
const isDesktop = useMediaQuery('(min-width: 1024px)')
const hasInlineContext = useMediaQuery('(min-width: 1280px)')

<main class="flex min-w-0 flex-1">
  <ChatPanel v-if="ui.state.view === 'chat'" />
  <DocumentsView v-else-if="ui.state.view === 'documents'" />
  <PromptGallery v-else />
</main>
```

**What's happening:**

Two breakpoints drive everything: below 1024 px the sidebar becomes a slide-in drawer (`ui.state.navOpen`, backdrop overlay, `role="dialog"` + `aria-modal`), and below 1280 px the context panel becomes a right drawer instead of an inline column. Escape closes dialogs first, then drawers (`onKeydown` in `App.vue`). `useMediaQuery` wraps `window.matchMedia` with SSR-safe listener cleanup.

**Why it matters:**

This is the entire "routing" of the app — one `v-if` chain on `ui.state.view`. Understanding it explains why state survives navigation (no component unmount of stores) and why there are no route URLs to bookmark: you always land on the chat view.

**Trace it further:** Byte 2 covers the three views themselves.

---

### Byte 2: The three views

**Builds on:** Byte 1

**Source files:** `frontend/src/components/ChatPanel.vue`, `frontend/src/components/DocumentsView.vue`, `frontend/src/components/PromptGallery.vue`, `frontend/src/components/WelcomeState.vue`

**In plain terms:**

`chat` is the workspace (header, messages or welcome page, composer); `documents` is the knowledge base (counts, uploader, list); `examples` is a searchable prompt gallery — each rendered by exactly one component.

**The code:**

```typescript
// ChatPanel.vue — two states: conversation vs. welcome homepage
<MessageList v-if="hasMessages" :messages="messages" @retry="chat.retryLast()" @inspect="onInspect" />
<div v-else class="min-h-0 flex-1 overflow-y-auto">
  <WelcomeState @select="onSelectExample" />
</div>
```

**What's happening:**

`ChatPanel`'s header shows live status (socket pill, knowledge-base count, clear, context toggle). With no messages it renders `WelcomeState` — quick-start cards, knowledge-base status/upload entry, and up to 4 recent conversations. `DocumentsView` re-runs `refresh()` + `checkHealth()` on mount and combines `DocumentUploader` + `DocumentList`. `PromptGallery` filters `PROMPT_CARDS + EXAMPLE_GALLERY` locally and, on selection, sets `ui.setPendingExample(prompt)` then switches to chat — the composer's watcher inserts the text without sending it.

**Why it matters:**

The pending-example handoff (`ui.state.pendingExample` → `ChatComposer` watcher → `consumePendingExample()`) is the only cross-view communication channel in the app — a pattern to copy (and to reset carefully; it is one-shot by design).

**Trace it further:** Byte 3 covers the chat interaction components.

---

### Byte 3: Chat rendering and streaming UI

**Builds on:** Byte 2, [11 — Orders and order history](11-orders-and-order-history.md), Byte 2

**Source files:** `frontend/src/components/MessageList.vue`, `frontend/src/components/MessageBubble.vue`, `frontend/src/components/ChatComposer.vue`

**In plain terms:**

Messages render as bubbles with status-dependent furniture (stage label, caret, error+retry, source chips), the list auto-scrolls only when you are already near the bottom, and the composer handles Enter-to-send, attachments, and the character limit.

**The code:**

```typescript
// MessageBubble.vue — status drives the UI
<p v-if="!message.content && message.status === 'streaming'" …>{{ stageLabel }}</p>
<MarkdownMessage v-else :content="message.content" />
<span v-if="message.status === 'streaming' && message.content" class="stream-caret" … />

// ChatComposer.vue — Enter sends, Shift+Enter breaks
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
```

**What's happening:**

`stageLabel` maps server stages to friendly copy ("Searching your documents…" / "Thinking…"). `MessageList` uses `useAutoScroll` (threshold 140 px): streaming only drags the view down if you were already at the bottom, otherwise a "Jump to latest" button appears. The composer auto-grows the textarea (max 220 px), shows a counter past 75% of `MAX_QUESTION_CHARS`, blocks over-limit sends, swaps Send↔Stop while generating, and accepts file attachments through the same `documents.uploadFiles()` pipeline as the Documents page.

**Why it matters:**

Nearly all chat-UX bugs live in this byte: scroll fighting, stage labels desyncing from events, or the counter letting oversized messages through. All three behaviors are covered by `components.spec.ts` and `chat.spec.ts`.

**Trace it further:** Byte 4 covers the side panels.

---

### Byte 4: Sidebar, context panel, and dialogs

**Builds on:** Byte 3

**Source files:** `frontend/src/components/AppSidebar.vue`, `frontend/src/components/TopNav.vue`, `frontend/src/components/ContextPanel.vue`, `frontend/src/components/SettingsDialog.vue`

**In plain terms:**

The chrome around the workspace: navigation + conversation search (sidebar), brand/status/theme/settings (top nav), three tabs of session context (right panel), and a diagnostics modal (settings).

**The code:**

```typescript
// ContextPanel.vue — the only tabbed surface
<div class="segmented">… sources | follow-ups | context …</div>
// 'sources' → SourcePanel (score bars + expandable previews)
// 'followups' → FollowUpPanel (static FOLLOW_UP_SUGGESTIONS, emits 'ask')
// 'context' → AssistantInfoCard + runtime dl (docs, chunks, connection)
```

**What's happening:**

`SourcePanel` reads `chat.currentSources` (pinned message or latest with sources) and shows per-chunk similarity bars and collapsible previews. `FollowUpPanel` buttons call `chat.sendMessage(prompt)` then close the panel. `AppSidebar` holds the searchable conversation list with two-click delete. `TopNav` closes its settings dropdown via a capture-phase document click listener (added/removed in `onMounted`/`onBeforeUnmount`). `SettingsDialog` closes on Escape, backdrop click, or its close button.

**Why it matters:**

The context panel is where retrieval transparency lives (source inspection originates in the message bubbles, Byte 3 of doc 06), and the dialogs demonstrate the app's accessibility conventions — `role="dialog"`, `aria-modal`, Escape handling, and focus-visible outlines — that any new overlay should follow.

**Trace it further:** Byte 5 covers the styling system.

---

### Byte 5: Styling — Tailwind v4 tokens and theming

**Builds on:** Byte 4

**Source files:** `frontend/src/style.css`, `frontend/index.html`, `frontend/src/stores/ui.ts`

**In plain terms:**

One 812-line stylesheet defines the whole design system: semantic CSS variables on `:root` for dark mode, redefined wholesale under `html.light`, mapped into Tailwind through `@theme inline`, plus component classes like `.btn` and `.chip`.

**The code:**

```css
/* frontend/src/style.css (shape of it) */
@import 'tailwindcss';

:root {
  --canvas: …; --surface: …; --ink: …; --muted: …; --faint: …;
  --accent: #7657ff; --accent-2: #438cff;
  --ok: …; --warn: …; --danger: …;
}
html.light { /* every variable redefined — one class swap = full repaint */ }

@theme inline {
  --color-accent: var(--accent);
  /* … maps tokens to Tailwind color/font utilities (Inter, JetBrains Mono) */
}
```

**What's happening:**

Theming is class-based: `ui.initTheme()`/`toggleTheme()` toggle `html.light`/`html.dark`, and every component using semantic tokens (`bg-surface`, `text-ink`, `border-line`) repaints with no per-component logic. `@theme inline` is Tailwind v4's CSS-native config — no `tailwind.config.js` exists. `index.html` loads with `class="dark"` so the first paint is dark before JS runs.

**Why it matters:**

The single-swap theming is why adding a color means touching `:root` + `html.light` (and optionally the `@theme` map) rather than dozens of components — and why missing a `html.light` override shows dark values in light mode, a common regression. The only external resource is Google Fonts in `index.html`; everything else bundles locally.

**Trace it further:** Byte 6 covers frontend–backend communication mechanics.

---

### Byte 6: Frontend–backend communication in practice

**Builds on:** Byte 3, [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 4

**Source files:** `frontend/src/services/api.ts`, `frontend/src/services/chatSocket.ts`, `frontend/src/config.ts`, `frontend/vite.config.ts`

**In plain terms:**

Plain HTTP goes through one `request<T>()` helper with a normalized `ApiError`; uploads use `XMLHttpRequest` for real progress events; chat uses a single lazily-opened WebSocket; and in dev, Vite proxies all four paths to the backend.

**The code:**

```typescript
// frontend/src/services/api.ts — one error shape for all callers
if (!response.ok) {
  let body: BackendErrorBody = {}
  try { body = (await response.json()) as BackendErrorBody } catch { /* proxy/HTML */ }
  throw new ApiError(body.code || 'HTTP_ERROR', body.message || `Request failed with status ${response.status}.`, response.status)
}

// frontend/vite.config.ts — dev proxy (HTTP + WebSocket)
'/health': { target: backendHttp }, '/upload': { … }, '/documents': { … },
'/ws': { target: backendWs, ws: true, changeOrigin: true },
```

**What's happening:**

`API_BASE_URL` defaults to `''` (same-origin), so in dev requests hit the Vite server and are proxied to `127.0.0.1:8000` (`VITE_DEV_BACKEND` overrides); setting `VITE_API_BASE_URL` in `frontend/.env` bypasses the proxy for a remote backend. `WS_URL` is derived (`ws://…/ws/chat`) or explicit. Uploads bypass `fetch()` deliberately: `fetch` cannot report upload progress, `xhr.upload.onprogress` can (0–99%, then 100% on success). Network failures become `ApiError('NETWORK_ERROR', …)` with actionable copy ("Make sure it is running on …").

**Why it matters:**

This is why the app works with zero frontend configuration locally, and why a *deployed* frontend pointed at a different-origin backend needs both CORS (`FRONTEND_ORIGIN`) and `VITE_API_BASE_URL` aligned — the two halves of the same setting (see [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md)).

---

## Continue learning

- [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) — the client-side filters these components use.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — where client-side validation sits.
- [18 — Testing and verification](18-testing-and-verification.md) — how these components are tested.
