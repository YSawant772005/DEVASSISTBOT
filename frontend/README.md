# DevAssist Frontend

Vue 3 (Composition API, `<script setup>`) + TypeScript + Vite + Tailwind v4.

See the [root README](../README.md) for setup and the full picture.

## Scripts

```powershell
npm run dev        # dev server on http://localhost:5173 (strict port)
npm run build      # vue-tsc type-check + production bundle into dist/
npm run preview    # serve the production build on http://localhost:4173
npm run typecheck  # vue-tsc only
npm test           # Vitest single run
npm run test:watch # Vitest watch mode
```

The dev server expects the backend at `http://localhost:8000`. Point it elsewhere
with `frontend/.env`:

```ini
VITE_API_BASE_URL=http://localhost:8000
# VITE_WS_URL=            # optional; derived from the API base when empty
```

`VITE_*` values are compiled into the bundle — never put secrets here. The Groq
key is used by the backend only.

## Structure

| Path | Contents |
|------|----------|
| `src/components/` | `TopNav`, `AppSidebar` (navigation + conversations), `ChatPanel`, `WelcomeState`, `MessageList`, `MessageBubble`, `MarkdownMessage`, `ChatComposer`, `DocumentsView`, `DocumentUploader`, `DocumentList`, `PromptGallery`, `ContextPanel`, `SourcePanel`, `FollowUpPanel`, `AssistantInfoCard`, `SettingsDialog`, `ui/ProgressBar` |
| `src/stores/` | Plain Vue reactivity stores: `documents`, `chat`, `ui` (no Pinia) |
| `src/services/` | `api.ts` (HTTP), `chatSocket.ts` (WebSocket client) |
| `src/data/promptCards.ts` | Quick-start cards + Examples gallery entries (title, description, icon, real prompt) |
| `src/utils/` | `markdown.ts` (markdown-it + highlight.js), `format.ts` |
| `src/composables/` | `useMediaQuery.ts` |
| `src/config.ts` | Public runtime config (upload limits, follow-up suggestions) |
| `src/style.css` | Tailwind v4 entry: design tokens, component classes, motion |
| `tests/` | Vitest specs (markdown, formatting, chat store, components, navigation) |

## UI notes

- Dark theme by default; a light theme is available via the `html.light` class.
- Four workspaces — **Chat**, **Documents**, **Examples**, **Settings** — reached
  from the top bar and the left navigation. The left nav is collapsible on
  desktop and becomes a drawer on tablet/mobile; the context panel is optional
  and opens inline on wide screens or as a drawer below 1280 px.
- The welcome homepage (no active conversation) shows the four quick-start cards,
  real knowledge-base guidance and recent conversations. Each card fills the
  composer with a real prompt.
- Documents live on a dedicated page with drag-and-drop upload, live progress,
  AND a searchable list with per-file deletion (click twice to confirm).
- The context panel has three tabs: **Sources** (real retrieval metadata),
  **Follow-ups** (static, labelled starters) and **Context** (actual runtime
  state). Relevance percentages come only from real cosine similarity scores.
- Chat history is session-only (browser memory); the FAISS index is backend
  memory and is cleared on restart. Both facts are surfaced in the UI.
- Markdown is rendered with `html: false`; code blocks are syntax-highlighted
  and have copy buttons. `prefers-reduced-motion` disables all motion.
