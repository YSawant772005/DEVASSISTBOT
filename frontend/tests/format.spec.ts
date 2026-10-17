import { describe, expect, it } from 'vitest'

import { validateFile } from '@/services/api'
import { formatBytes, relativeTime, titleFromMessage, truncate } from '@/utils/format'

describe('formatBytes', () => {
  it('formats each unit', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('handles invalid input', () => {
    expect(formatBytes(-1)).toBe('—')
    expect(formatBytes(Number.NaN)).toBe('—')
  })
})

describe('relativeTime', () => {
  it('describes recency', () => {
    const now = Date.now()
    expect(relativeTime(now, now)).toBe('just now')
    expect(relativeTime(now - 5 * 60 * 1000, now)).toBe('5m ago')
    expect(relativeTime(now - 3 * 60 * 60 * 1000, now)).toBe('3h ago')
    expect(relativeTime(now - 2 * 24 * 60 * 60 * 1000, now)).toBe('2d ago')
  })
})

describe('truncate / titleFromMessage', () => {
  it('truncates long text with an ellipsis', () => {
    expect(truncate('abcdef', 4)).toBe('abc…')
    expect(truncate('abc', 10)).toBe('abc')
  })

  it('creates a conversation title from a question', () => {
    expect(titleFromMessage('  How do   I fix this?  ')).toBe('How do I fix this?')
    expect(titleFromMessage('')).toBe('New conversation')
    expect(titleFromMessage('x'.repeat(80)).length).toBeLessThanOrEqual(42)
  })
})

function makeFile(name: string, size: number): File {
  const file = new File(['x'], name)
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('validateFile', () => {
  it('accepts supported extensions under the size limit', () => {
    expect(validateFile(makeFile('notes.md', 100)).ok).toBe(true)
    expect(validateFile(makeFile('spec.pdf', 100)).ok).toBe(true)
    expect(validateFile(makeFile('log.TXT', 100)).ok).toBe(true)
  })

  it('rejects unsupported types', () => {
    const result = validateFile(makeFile('image.png', 100))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.message).toContain('not a supported file type')
  })

  it('rejects files above 5 MB', () => {
    const result = validateFile(makeFile('big.md', 6 * 1024 * 1024))
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.message).toContain('5 MB')
  })

  it('rejects empty files', () => {
    const result = validateFile(makeFile('empty.txt', 0))
    expect(result.ok).toBe(false)
  })
})
