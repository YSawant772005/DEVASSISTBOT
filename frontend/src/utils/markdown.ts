/**
 * Assistant Markdown rendering.
 *
 * Raw HTML in model output is escaped (``html: false``) so untrusted content
 * cannot execute scripts. Fenced code blocks are highlighted with
 * highlight.js and wrapped in a block that offers a copy button.
 *
 * markdown-it 15 ships its own TypeScript types; the default export is the
 * constructor and the ``MarkdownIt`` *type* describes an instance.
 */

import hljs from 'highlight.js/lib/common'
import MarkdownItConstructor, { type MarkdownIt, type RendererRule } from 'markdown-it'

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ESCAPES[char] as string)
}

function normalizeLanguage(language: string): string | null {
  if (!language || language === 'text' || language === 'plain' || language === 'txt') {
    return null
  }
  const normalized = language.toLowerCase()
  if (normalized === 'js') return 'javascript'
  if (normalized === 'ts') return 'typescript'
  if (normalized === 'py') return 'python'
  if (normalized === 'sh' || normalized === 'shell' || normalized === 'zsh') return 'bash'
  if (normalized === 'yml') return 'yaml'
  return normalized
}

function renderCodeBlock(code: string, language: string): string {
  const normalized = normalizeLanguage(language)
  let body: string

  if (normalized && hljs.getLanguage(normalized)) {
    try {
      body = hljs.highlight(code, { language: normalized, ignoreIllegals: true }).value
    } catch {
      body = escapeHtml(code)
    }
  } else {
    body = escapeHtml(code)
  }

  const label = escapeHtml(normalized || language || 'text')
  return (
    `<div class="code-block">` +
    `<div class="code-block__bar"><span class="code-block__lang">${label}</span>` +
    `<button type="button" class="code-block__copy" data-copy-code>Copy</button></div>` +
    `<pre><code class="hljs">${body}</code></pre>` +
    `</div>`
  )
}

export const md: MarkdownIt = new MarkdownItConstructor({
  html: false, // never execute raw HTML from model or document output
  linkify: true,
  breaks: false,
  typographer: false,
})

// Render fenced blocks ourselves. Returning a <div> from the `highlight` option
// would still be wrapped by markdown-it in its own <pre><code> element, so the
// fence renderer is replaced outright.
md.renderer.rules.fence = (tokens, index) => {
  const token = tokens[index]
  const rawLanguage = (token.info || '').trim().split(/\s+/)[0] ?? ''
  return renderCodeBlock(token.content, rawLanguage)
}

const defaultLinkOpen: RendererRule =
  md.renderer.rules.link_open ??
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))

md.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, index, options, env, self)
}

export function renderMarkdown(source: string): string {
  if (!source) return ''
  return md.render(source)
}

export function extractFirstHeading(source: string): string | null {
  const match = /^#{1,3}\s+(.+)$/m.exec(source)
  return match ? match[1].replace(/[`*_]/g, '').trim() : null
}
