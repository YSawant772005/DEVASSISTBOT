import { describe, expect, it } from 'vitest'

import { escapeHtml, extractFirstHeading, renderMarkdown } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('renders headings, emphasis, lists and links', () => {
    const html = renderMarkdown(
      '# Title\n\nSome **bold** and _italic_ text.\n\n- one\n- two\n\n[link](https://example.com)',
    )

    expect(html).toContain('<h1>Title</h1>')
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('<em>italic</em>')
    expect(html).toContain('<li>one</li>')
    expect(html).toContain('<a href="https://example.com"')
  })

  it('adds safe attributes to links', () => {
    const html = renderMarkdown('[docs](https://example.com)')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('escapes raw HTML instead of executing it', () => {
    const html = renderMarkdown('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>')

    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;script&gt;')
  })

  it('does not allow javascript: links', () => {
    const html = renderMarkdown('[click me](javascript:alert(1))')
    // markdown-it refuses to emit an anchor at all: the text stays literal.
    expect(html).not.toContain('<a href="javascript')
    expect(html).not.toContain('<a href')
  })

  it('renders a fenced code block with language label and copy button', () => {
    const html = renderMarkdown('```python\ndef add(a, b):\n    return a + b\n```')

    expect(html).toContain('class="code-block"')
    expect(html).toContain('data-copy-code')
    expect(html).toContain('<span class="code-block__lang">python</span>')
    expect(html).toContain('hljs')

    // Highlighting wraps tokens in spans, so compare the visible text.
    const text = html.replace(/<[^>]+>/g, '')
    expect(text).toContain('def add(a, b):')
    expect(text).toContain('return a + b')
  })

  it('escapes HTML inside code blocks', () => {
    const html = renderMarkdown('```html\n<script>alert("x")</script>\n```')
    // Highlighting interleaves spans, so assert on the absence of a live tag
    // rather than on a contiguous escaped sequence.
    expect(html).not.toContain('<script>alert')
    expect(html).toContain('&lt;')
    expect(html).toContain('class="code-block"')
  })

  it('handles unknown languages without highlighting', () => {
    const html = renderMarkdown('```klingon\nnuqneH\n```')
    expect(html).toContain('nuqneH')
    expect(html).toContain('klingon')
  })

  it('normalises common language aliases', () => {
    expect(renderMarkdown('```js\nconst a = 1\n```')).toContain('javascript')
    expect(renderMarkdown('```py\nx = 1\n```')).toContain('python')
  })

  it('returns an empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
  })
})

describe('escapeHtml', () => {
  it('escapes all dangerous characters', () => {
    expect(escapeHtml(`<>&"'`)).toBe('&lt;&gt;&amp;&quot;&#39;')
  })
})

describe('extractFirstHeading', () => {
  it('finds the first heading', () => {
    expect(extractFirstHeading('intro\n\n## My title\ntext')).toBe('My title')
  })

  it('returns null when there is no heading', () => {
    expect(extractFirstHeading('just text')).toBeNull()
  })
})
