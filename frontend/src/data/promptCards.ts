/**
 * Welcome quick-start cards and the Examples gallery entries.
 *
 * Every entry carries a real prompt that is submitted through the normal chat
 * flow, so nothing here is decorative.
 */
import {
  Bug,
  BookOpen,
  Braces,
  Database,
  FileSearch,
  GitBranch,
  GraduationCap,
  Layers,
  ShieldCheck,
  Sparkles,
  TestTube2,
  Wrench,
} from 'lucide-vue-next'
import type { Component } from 'vue'

export interface PromptCard {
  id: string
  title: string
  description: string
  /** The example prompt inserted into the composer. */
  prompt: string
  icon: Component
}

/** The four primary quick-start actions on the welcome homepage. */
export const PROMPT_CARDS: PromptCard[] = [
  {
    id: 'explain',
    title: 'Explain code',
    description: 'Understand unfamiliar code step by step.',
    prompt: 'Explain what this function does and why.',
    icon: Braces,
  },
  {
    id: 'debug',
    title: 'Debug an error',
    description: 'Investigate an exception or unexpected behavior.',
    prompt: 'Help me identify the root cause of this error.',
    icon: Bug,
  },
  {
    id: 'documents',
    title: 'Ask my documents',
    description: 'Get answers based on uploaded technical files.',
    prompt: 'Summarize the architecture described in my uploaded document.',
    icon: FileSearch,
  },
  {
    id: 'concept',
    title: 'Learn a concept',
    description: 'Learn a programming concept with examples.',
    prompt: 'Explain async/await with a practical example.',
    icon: GraduationCap,
  },
]

/** Additional curated starters for the Examples gallery. */
export const EXAMPLE_GALLERY: PromptCard[] = [
  {
    id: 'sample-explain',
    title: 'Explain this code',
    description: 'Walk through a snippet line by line and flag risky parts.',
    prompt:
      'Explain what this code does and point out anything risky:\n\n```python\ndef load(path):\n    f = open(path)\n    return f.read().split(",")\n```',
    icon: BookOpen,
  },
  {
    id: 'sample-debug',
    title: 'Debug a stack trace',
    description: 'Turn an exception into a concrete fix.',
    prompt:
      'I get `TypeError: cannot unpack non-sequence NoneType` when I run this. How do I fix it?\n\n```python\ndef parse(line):\n    if ":" in line:\n        return line.split(":", 1)\n```',
    icon: Bug,
  },
  {
    id: 'sample-review',
    title: 'Review my design',
    description: 'Get feedback on trade-offs and failure modes.',
    prompt:
      'Review this module boundary. What are the risks, and how would you decouple it? Focus on testability.',
    icon: Layers,
  },
  {
    id: 'sample-tests',
    title: 'Write a test',
    description: 'Generate a focused unit test for a function.',
    prompt:
      'Write a minimal unit test for this function, including one edge case:\n\n```python\ndef median(values):\n    return sorted(values)[len(values) // 2]\n```',
    icon: TestTube2,
  },
  {
    id: 'sample-query',
    title: 'Optimize a query',
    description: 'Reason about performance and indexes.',
    prompt:
      'This query is slow on a large table. Suggest indexes and a rewrite:\n\n```sql\nSELECT * FROM events WHERE user_id = 42 ORDER BY created_at DESC LIMIT 20;\n```',
    icon: Database,
  },
  {
    id: 'sample-git',
    title: 'Untangle Git history',
    description: 'Recover from a messy branch state.',
    prompt:
      'I accidentally committed to `main` and want to move the last two commits to a new branch. Show the exact commands.',
    icon: GitBranch,
  },
  {
    id: 'sample-refactor',
    title: 'Refactor safely',
    description: 'Improve structure without breaking behavior.',
    prompt:
      'Refactor this function into smaller, testable pieces without changing its behavior:\n\n```js\nasync function sync(items) {\n  for (const item of items) {\n    const res = await fetch("/api/sync", { method: "POST", body: JSON.stringify(item) })\n    if (!res.ok) throw new Error("sync failed: " + item.id)\n  }\n}\n```',
    icon: Wrench,
  },
  {
    id: 'sample-security',
    title: 'Harden an endpoint',
    description: 'Spot security gaps before shipping.',
    prompt:
      'Review this handler for security issues (injection, authz, secrets, error leakage) and propose fixes.',
    icon: ShieldCheck,
  },
  {
    id: 'sample-perf',
    title: 'Diagnose slow code',
    description: 'Find the bottleneck and measure it.',
    prompt: 'This data pipeline is slow. Suggest a profiling plan and likely hot spots.',
    icon: Sparkles,
  },
]
