# 12 — Wishlist

**Overview:** There is **no wishlist** in this repository — no saved/favorited items, no per-user wishlists, no duplicate-add handling, and no wishlist UI (verified by search; there are no users at all). This document states that absence, then maps the topic onto the features that genuinely fill the same niche: the **static curated prompt collections** (welcome quick-starts and the Examples gallery) and the **only persistent user preference**, the theme toggle.

**Scope:** Verified absence of wishlist mechanics; curated prompt lists as the closest "saved items" feature; the theme as the only persisted preference; and what a real wishlist feature would require. User-association and duplicate-handling concepts are addressed as non-applicable.

**Prerequisites:** [08 — Cart and session management](08-cart-and-session-management.md), [11 — Orders and order history](11-orders-and-order-history.md).

**Important source files:**
- `frontend/src/data/promptCards.ts`
- `frontend/src/components/PromptGallery.vue`
- `frontend/src/components/WelcomeState.vue`
- `frontend/src/stores/ui.ts`

---

### Byte 1: Verified absence of a wishlist

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `frontend/src/` (whole tree)

**In plain terms:**

A wishlist needs three things this app does not have: identified users, saved-item state, and a place to show it. None exist — the only browser storage in the entire frontend is one theme key.

**The code:**

```text
# Verified by searching frontend/src/ for persistence and save-like APIs:
- localStorage usage: exactly one key, 'devassist-theme'  (stores/ui.ts)
- No 'favorite', 'bookmark', 'save', 'wishlist' APIs or state in any store
- No user identity to associate saved items with (no auth — see doc 10)
```

**What's happening:**

The absence is structural, not an oversight: with no accounts, there is nothing to associate a wishlist *to*, and with session-only state, saved items would not survive reload anyway.

**Why it matters:**

Stating this first keeps the remainder honest: the following bytes cover the real, shipped features that occupy the wishlist's conceptual slot rather than speculating.

**Trace it further:** Byte 2 introduces the curated collections.

---

### Byte 2: The "saved items" that do exist — static prompt collections

**Builds on:** Byte 1

**Source files:** `frontend/src/data/promptCards.ts`, `frontend/src/components/WelcomeState.vue`, `frontend/src/components/PromptGallery.vue`

**In plain terms:**

The app ships two curated, read-only collections of starter prompts — four quick-starts on the welcome page and a twelve-card Examples gallery — that behave like a fixed "saved list" a user can browse and launch.

**The code:**

```typescript
// frontend/src/data/promptCards.ts
export interface PromptCard {
  id: string
  title: string
  description: string
  prompt: string
  icon: Component
}
export const PROMPT_CARDS: PromptCard[] = [ /* 4 welcome quick-starts */ ]
export const EXAMPLE_GALLERY: PromptCard[] = [ /* 8 curated examples */ ]
```

**What's happening:**

Both are plain module-level constants — no fetching, no store, no mutation. `WelcomeState` renders `PROMPT_CARDS` as quick-start buttons; `PromptGallery` renders `PROMPT_CARDS + EXAMPLE_GALLERY` as a searchable grid (local `query` ref, client-side `includes` filtering). Clicking a card sets `ui.setPendingExample(card.prompt)` and switches to the chat view, where `ChatComposer`'s watcher inserts the text into the draft **without sending it**.

**Why it matters:**

This is the closest analogue to "browsing saved items": fixed content, click to load, no persistence or personalization. Adding/removing cards means editing source code and rebuilding — there is no runtime management UI (contrast with the document catalog, which does have runtime management in [14 — Admin dashboard and management](14-admin-dashboard-and-management.md)).

**Trace it further:** Byte 3 covers the one persistent preference.

---

### Byte 3: The only persisted preference — theme

**Builds on:** Byte 1, [08 — Cart and session management](08-cart-and-session-management.md), Byte 5

**Source files:** `frontend/src/stores/ui.ts`, `frontend/src/style.css`

**In plain terms:**

The dark/light theme choice is written to `localStorage` and restored on load — the app's entire persistence layer, one string.

**The code:**

```typescript
// frontend/src/stores/ui.ts
function toggleTheme(): void {
  state.theme = state.theme === 'dark' ? 'light' : 'dark'
  try {
    localStorage.setItem(THEME_KEY, state.theme)   // 'devassist-theme'
  } catch {
    // Storage may be unavailable (private mode); theme still applies in memory.
  }
  applyTheme()
}
```

**What's happening:**

`applyTheme()` toggles `html.light`/`html.dark` classes; `style.css` redefines all design tokens under `html.light`, so one class swap repaints the app. `initTheme()` (called from `App.vue` on mount) validates the stored value — anything other than `'light'`/`'dark'` falls back to dark. Both read and write are try/catch-guarded for private-browsing environments.

**Why it matters:**

This is the working template for *any* future preference persistence: a namespaced key, validated values, guarded access, and a safe in-memory fallback. It is also the answer to "why doesn't anything else remember me?" — extending persistence beyond this one key is a deliberate feature decision.

**Trace it further:** Byte 4 covers duplicate handling — or rather, why the nearest cases are trivial.

---

### Byte 4: Duplicate handling — the nearest real analogues

**Builds on:** Byte 2

**Source files:** `frontend/src/stores/documents.ts`, `frontend/src/stores/chat.ts`, `frontend/src/stores/ui.ts`

**In plain terms:**

There is no duplicate-wishlist-item problem to solve, but the app does guard three adjacent "same thing twice" cases: uploading the same file twice, double-sending while generating, and re-consuming a one-shot prompt.

**The code:**

```typescript
// frontend/src/stores/ui.ts — one-shot consumption prevents double use
function consumePendingExample(): string | null {
  const prompt = state.pendingExample
  state.pendingExample = null      // cleared immediately after being read
  return prompt
}

// frontend/src/stores/chat.ts — concurrent send guard
if (!question || state.isGenerating) return
```

**What's happening:**

Note what is *not* guarded: uploading `notes.md` twice creates two documents with two `doc_id`s (no filename dedupe — verified in `add_document`, which always mints a new uuid), each fully re-embedded. The guards that exist protect interaction semantics: the pending example is consumed exactly once, and a second send while streaming is refused both client-side (`isGenerating`) and server-side (`BUSY`).

**Why it matters:**

Documenting real versus absent dedupe matters operationally: re-uploading a large PDF doubles index size and memory, and there is no warning. If you add dedupe, hashing `data` inside `upload_document()` before `add_document()` is the natural insertion point.

**Trace it further:** Byte 5 summarizes the non-applicable wishlist mechanics.

---

### Byte 5: Wishlist mechanics that do not apply

**Builds on:** Byte 1, Byte 4

**Source files:** `frontend/src/stores/ui.ts` (evidence of what exists instead)

**In plain terms:**

Every standard wishlist behavior — add/remove from a product page, persistence per user, "already saved" feedback, a wishlist page, availability notices — has no counterpart here and no hidden partial implementation.

**The code:**

```text
Wishlist mechanic          Status in this repository
─────────────────────────  ─────────────────────────────────────────────
Add/remove items           No equivalent (documents can be added/removed —
                           that is the catalog, see doc 05)
Persistence                Only 'devassist-theme' (Byte 3)
Duplicate detection        None for documents; one-shot guards for prompts (Byte 4)
User association           No users exist (see doc 10)
Wishlist page              No equivalent; Examples gallery is the closest
                           browsable collection (Byte 2)
Availability/stock alerts  Non-applicable; /health counts instead (doc 06, Byte 3)
```

**What's happening:**

This table is the byte — it exists so a reader auditing "wishlist coverage" can confirm nothing was invented and nothing shipped.

**Why it matters:**

Filling requirement "if a feature does not apply, explain the fact and document the closest relevant equivalent" with a single-glance reference, backed by the verified absence in Byte 1.

**Trace it further:** [05 — Product catalog](05-product-catalog.md) documents the collection features that *are* real.

---

## Continue learning

- [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) — the real management UI for the collection that exists.
- [17 — Contact, newsletter, and static pages](17-contact-newsletter-and-static-pages.md) — other static content surfaces.
- [15 — Frontend views, JavaScript, and CSS](15-frontend-views-javascript-css.md) — where the prompt cards render.
