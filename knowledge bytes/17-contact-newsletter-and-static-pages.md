# 17 — Contact, Newsletter, and Static Pages

**Overview:** This document covers the "content surfaces" of DevAssist: the pages, cards, and static copy a user reads without sending a message. Honest headline: **there is no contact form, no newsletter signup, and no server-rendered static site.** DevAssist is a single-page Vue application; everything below documents the static content that *does* exist — the welcome page, the prompt gallery, the scope card, the settings dialog, and the HTML shell — plus what a real contact/newsletter feature would require, mapped onto existing patterns.

**Scope:** The SPA's static content surfaces (WelcomeState, PromptGallery, AssistantInfoCard, SettingsDialog), the `index.html` shell and its only external dependency (Google Fonts), and an explicit absence statement for contact/newsletter/forms.

**Prerequisites:** [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md), [13 — Reviews and moderation](13-reviews-and-moderation.md) (topic policy, which these surfaces reinforce).

**Important source files:**
- `frontend/index.html`
- `frontend/src/components/WelcomeState.vue`
- `frontend/src/components/PromptGallery.vue`
- `frontend/src/components/AssistantInfoCard.vue`
- `frontend/src/components/SettingsDialog.vue`
- `frontend/src/data/promptCards.ts`

---

### Byte 1: There is no contact or newsletter feature — and that's a design fact, not an omission

**Builds on:** [00 — Project architecture](00-project-architecture.md)

**Source files:** `backend/app/main.py` (route inventory), `frontend/src/App.vue` (view inventory)

**In plain terms:**

The backend exposes exactly four HTTP routes (`/`, `/health`, `/upload`, `/documents`) plus the WebSocket at `/ws/chat`. None of them accept email addresses, subscription requests, or free-form contact messages. The frontend's view state (`ui.state.view`) switches between chat, documents, and examples — there is no "contact" or "about" route at all.

**The code:**

```python
# backend/app/main.py — the complete route surface (names only)
app = create_app()   # mounts: GET /  GET /health
                     # api/upload.py:    POST /upload, GET /documents,
                     #                   DELETE /documents, DELETE /documents/{id}
                     # api/chat_ws.py:   WS   /ws/chat
```

```ts
// frontend/src/stores/ui.ts — the complete view set
export type View = 'chat' | 'documents' | 'examples'   // no 'contact', no 'static pages'
```

**What's happening:**

An e-commerce template's "Contact Us" page, newsletter footer, or mailing-list modal has no counterpart here, because the app has no user accounts, no email transport, and no backend persistence to record submissions. Adding one would require: a new FastAPI route, a Pydantic schema for the payload, storage (currently absent — see [03 — Data layer and database](03-data-layer-and-database.md)), and probably an email provider integration (currently the only external API is Groq, and it is key-gated server-side).

**Why it matters:**

If you are reading these documents expecting a storefront's static pages: they do not exist, and nothing in the codebase pretends they do. The closest real equivalents are documented below so the knowledge transfers — the pattern of "static, data-driven content components" is the same whether the content is prompt cards or product banners.

**Trace it further:** The absence inventory in [09 — Checkout and coupons](09-checkout-and-coupons.md) and [12 — Wishlist](12-wishlist.md) follows the same method: enumerate the actual routes, then state what is not there.

---

### Byte 2: The welcome page is real UI wired to real stores

**Builds on:** Byte 1

**Source files:** `frontend/src/components/WelcomeState.vue`, `frontend/src/data/promptCards.ts`

**In plain terms:**

The home screen shown when no conversation is active looks like marketing copy, but every element is functional: prompt cards fill the composer, the upload button runs the real ingestion pipeline, and the "recent conversations" list reads from the in-memory chat store.

**The code:**

```vue
<!-- frontend/src/components/WelcomeState.vue -->
function onFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return
  void documents.uploadFiles(files)   // the same store action the sidebar uses
  ui.setView('documents')
}

const recent = computed(() =>
  [...chat.state.conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 4),
)
```

**What's happening:**

The welcome state renders three zones: an intro banner, a grid over `PROMPT_CARDS` (static data from `promptCards.ts`), and a knowledge-base guidance panel that switches between "No documents indexed yet" and a document-count summary depending on `documents.state.documents.length`. Animation delays are staggered per card index (`animationDelay: ${80 + index * 55}ms`) for a cascading entrance. Recent conversations are sorted by `updatedAt` descending — timestamps held only in memory, so this list resets on reload.

**Why it matters:**

This is the pattern of a "static page" done right in an SPA: no fake links, no dead buttons. Each card's `@click="onSelect(card.prompt)"` emits into the chat composer rather than navigating to a placeholder page. Compare with an e-commerce landing page — the structure is the same (hero, cards, guidance), but here the data source is Pinia stores instead of a CMS.

**Trace it further:** [04 — Models and viewmodels](04-models-and-viewmodels.md) for the `PromptCard` shape; [02 — Application startup and request flow](02-application-startup-and-request-flow.md) for what happens after `uploadFiles()` is called.

---

### Byte 3: The prompt gallery — the app's "examples page," with client-side search

**Builds on:** Byte 2

**Source files:** `frontend/src/components/PromptGallery.vue`, `frontend/src/data/promptCards.ts`

**In plain terms:**

The Examples view is the closest thing to a static content page: a searchable gallery of pre-written programming prompts. It merges two static arrays and filters them with a computed property — no server, no router query parameters.

**The code:**

```ts
// frontend/src/components/PromptGallery.vue
const all: PromptCard[] = [...PROMPT_CARDS, ...EXAMPLE_GALLERY]

const filtered = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return all
  return all.filter(
    (card) =>
      card.title.toLowerCase().includes(term) ||
      card.description.toLowerCase().includes(term) ||
      card.prompt.toLowerCase().includes(term),
  )
})

function useCard(card: PromptCard): void {
  ui.setPendingExample(card.prompt)   // hand off to the composer, don't auto-send
  ui.setView('chat')
}
```

**What's happening:**

The gallery deliberately does two user-respecting things. First, selecting a card sets a *pending example* and switches views — the prompt lands in the composer for editing rather than firing a request immediately. Second, the empty state (`No prompts match "{{ query }}"`) offers a direct escape hatch to the composer. Filtering is O(n) over a handful of cards, so a computed property is the right tool; there is no debouncing or pagination because there is nothing to paginate.

**Why it matters:**

If you were building the storefront equivalent (a "featured products" page), this is the exact template: static data module → computed filter → click that flows into the transactional view. Keeping content in `src/data/` rather than inline in the component means the copy can change without touching component logic — and the content is trivially testable.

**Trace it further:** [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md) for how the examples view fits the layout shell; `frontend/tests/navigation.spec.ts` covers view switching.

---

### Byte 4: Scope-setting copy is part of the product's safety story

**Builds on:** [13 — Reviews and moderation](13-reviews-and-moderation.md), Byte 2

**Source files:** `frontend/src/components/AssistantInfoCard.vue`

**In plain terms:**

The sidebar's "Programming-only assistant" card is static content with a job beyond decoration: it tells the user what the backend's topic policy will and won't do — and it is honest about the limits of prompt-based filtering.

**The code:**

```vue
<!-- frontend/src/components/AssistantInfoCard.vue -->
<p class="mt-2.5 border-t border-line pt-2 text-[0.62rem] leading-relaxed text-faint">
  Off-topic requests are politely declined. Topic filtering is best-effort prompt guidance,
  not a guarantee.
</p>
```

**What's happening:**

The card lists four capabilities (programming & debugging, algorithms, architecture, technical documentation) driven by a local `capabilities` array with Lucide icons. The disclaimer sentence mirrors the server-side policy text in `backend/app/prompts/`: the system prompt instructs the model to decline off-topic questions, but since that is prompt guidance rather than a hard classifier, the UI says so. This is verified behavior — see the policy tests in [18 — Testing and verification](18-testing-and-verification.md) (`test_policy_refusal_is_streamed_as_tokens`).

**Why it matters:**

Static copy that accurately describes system behavior is a trust feature. The alternative — claiming "AI moderation guarantees safe answers" — would be a false claim the code cannot back. When writing your own static pages, treat the UI's promises as part of the contract you must be able to test.

**Trace it further:** Byte 5 for where the disclaimer's behavior is enforced; [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the full control inventory.

---

### Byte 5: The settings dialog is a static page fed by a live endpoint — with no secrets

**Builds on:** Byte 1, [02 — Application startup and request flow](02-application-startup-and-request-flow.md)

**Source files:** `frontend/src/components/SettingsDialog.vue`, `frontend/src/config.ts`

**In plain terms:**

The Settings dialog is the app's "About/status" page. On mount it calls the documents store's `checkHealth()`, which hits `GET /health`, and renders backend URL, WebSocket URL, model name, index size, and provider status. It explicitly contains no credentials.

**The code:**

```vue
<!-- frontend/src/components/SettingsDialog.vue -->
/**
 * Settings dialog: live backend diagnostics read from GET /health.
 * Contains no secrets — the Groq key stays on the backend.
 */
onMounted(() => { void refresh() })

async function refresh(): Promise<void> {
  checking.value = true
  await documents.checkHealth()
  checking.value = false
}
```

```vue
<dt class="text-muted">Backend URL</dt>
<dd class="font-mono text-[0.7rem] text-ink">{{ API_BASE_URL }}</dd>
<dt class="text-muted">WebSocket</dt>
<dd class="truncate font-mono text-[0.7rem] text-ink" :title="WS_URL">{{ WS_URL }}</dd>
```

**What's happening:**

The dialog is a modal (`role="dialog"`, `aria-modal="true"`, Escape-to-close via `onKeydown`) that mixes static labels with live data. The theme toggle (Sun/Moon icons) writes the `devassist-theme` localStorage key — the app's only client-side persistence. Because `/health` returns `status: "degraded"` when `GROQ_API_KEY` is absent (see [18 — Testing and verification](18-testing-and-verification.md), `test_health_returns_degraded_without_credentials`), the dialog doubles as a configuration troubleshooting surface.

**Why it matters:**

An "About" page that leaks configuration is a real vulnerability class (think of debug panels left enabled in production). Here the design rule is enforced in a code comment *and* in architecture: the Groq key never crosses the network boundary, so there is nothing for the dialog to accidentally reveal. Your static pages should follow the same discipline: display what helps the user, never what helps an attacker.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the `/health` payload shape; [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) for using the dialog's diagnostics when a deployment misbehaves.

---

### Byte 6: `index.html` — the whole "static site," and its one external dependency

**Builds on:** Byte 1

**Source files:** `frontend/index.html`

**In plain terms:**

The entire server-delivered static shell is 23 lines: a description meta tag, the page title, an SVG favicon, two Google Fonts preconnects, and the `#app` mount point.

**The code:**

```html
<!-- frontend/index.html -->
<title>DevAssist — Your Programming Assistant</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
  rel="stylesheet"
/>
```

**What's happening:**

Google Fonts is the **only** external network reference in the entire frontend. There are no analytics scripts, no chat widgets, no CDN JavaScript — which means no third-party script can inject itself into the app, and CSP reviewers have exactly one origin to allowlist (plus the Vite/cloudflared hosts during development). The `<html lang="en" class="dark">` default class sets the dark theme before Vue hydrates, avoiding a flash of light theme.

**Why it matters:**

For a demo deployed behind a quick tunnel (see [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md)), this minimal shell matters: the only thing that can fail before the JS bundle loads is a font fetch, and the app degrades to system fonts. If your environment blocks `fonts.googleapis.com` entirely, delete the two `<link>` tags — nothing else depends on them.

**Trace it further:** [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md) for how Tailwind and the CSS variables pick up these fonts; [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) for serving this shell in production.

---

## Continue learning

- If you want to add a real contact form: follow the upload route pattern in [09 — Checkout and coupons](09-checkout-and-coupons.md) (mapped equivalent) — Pydantic schema → FastAPI route → error envelope from `core/errors.py`. You would also need to decide on storage; [03 — Data layer and database](03-data-layer-and-database.md) explains why there is currently none.
- If you want to extend the prompt gallery with user-saved prompts: start with `ui.setPendingExample` in [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md) and note that any persistence must be localStorage (like the theme key) or a new backend endpoint.
- To verify the policy claims made in Byte 4 yourself, run the backend suite described in [18 — Testing and verification](18-testing-and-verification.md).
