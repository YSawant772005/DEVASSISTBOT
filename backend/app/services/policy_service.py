"""Programming-only policy.

The primary guardrail is the system prompt (see ``app.prompts.system_prompt``).
On top of that, a deliberately conservative heuristic declines requests that
are *clearly* unrelated to programming and contain no technical signal at all.
It is best-effort: any technical keyword wins, so ambiguous wording such as
"temperature" in a machine-learning context is never rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REFUSAL_MESSAGE = (
    "I'm DevAssist, a programming-focused assistant, so I can only help with "
    "software development topics like coding, debugging, algorithms, "
    "architecture and developer tooling. Please ask me a programming question."
)

# Any hit here means the request is treated as programming-related.
_TECH_SIGNALS = (
    "code", "coding", "program", "programming", "developer", "software", "function",
    "class", "method", "variable", "const", "let ", "def ", "import ", "return",
    "compile", "compiler", "runtime", "syntax", "debug", "bug", "error", "exception",
    "traceback", "stack trace", "stacktrace", "log", "test", "unit test", "pytest",
    "jest", "vitest", "lint", "refactor", "algorithm", "data structure", "array",
    "list", "dict", "hashmap", "hash map", "set", "queue", "stack", "tree", "graph",
    "recursion", "recursive", "loop", "iteration", "complexity", "big o", "sort",
    "python", "javascript", "typescript", "java", "kotlin", "swift", "golang", " go ",
    "rust", "c++", "c#", "php", "ruby", "scala", "sql", "nosql", "mongodb", "postgres",
    "mysql", "sqlite", "redis", "html", "css", "sass", "react", "vue", "angular",
    "svelte", "next.js", "node", "deno", "bun", "django", "flask", "fastapi", "express",
    "spring", "rails", "laravel", ".net", "api", "rest", "graphql", "grpc", "endpoint",
    "http", "https", "websocket", "json", "yaml", "xml", "regex", "regular expression",
    "git", "github", "gitlab", "branch", "commit", "merge", "pull request", "docker",
    "kubernetes", "container", "linux", "bash", "powershell", "terminal", "shell",
    "cli", "command line", "server", "client", "database", "query", "index", "schema",
    "migration", "cache", "thread", "process", "async", "await", "promise", "concurrency",
    "memory", "pointer", "malloc", "garbage collection", "interface", "struct", "enum",
    "dependency", "package", "library", "framework", "npm", "pip", "maven", "gradle",
    "deploy", "deployment", "ci/cd", "devops", "architecture", "design pattern",
    "microservice", "monolith", "machine learning", "model", "neural", "dataset",
    "pandas", "numpy", "pytorch", "tensorflow", "embedding", "vector", "rag",
    "language model", "llm", "prompt", "token", "system design", "scalab", "latency",
    "throughput", "benchmark", "profiler", "ide", "editor", "vscode", "vim", "keyboard",
    "shortcut", "documentation", "readme", "stack overflow", "security", "vulnerab",
    "xss", "sql injection", "encryption", "hash", "jwt", "oauth", "authentication",
    "authorization", "webpack", "vite", "tailwind", "bootstrap", "figma", "ui", "ux",
    "frontend", "backend", "full stack", "mobile app", "android", "ios", "windows",
    "macos", "operating system", "kernel", "network", "protocol", "tcp", "udp", "dns",
    "load balancer", "queue", "kafka", "rabbitmq", "message broker", "etl", "csv",
    "print", "console", "output", "input", "string", "integer", "float", "boolean",
    "null", "none", "undefined", "slice", "iterate", "annotat", "type hint", "generics",
    "closure", "callback", "decorator", "middleware", "route", "migration", "orm",
)

# Only used when there is no technical signal at all.
_OFF_TOPIC_SIGNALS = (
    "weather", "forecast", "temperature outside", "recipe", "cook", "cooking", "bake",
    "baking", "dinner idea", "restaurant", "celebrity", "gossip", "movie recommend",
    "film recommend", "song lyric", "lyrics", "music album", "horoscope", "astrology",
    "astrolog", "football", "soccer", "basketball", "nba", "nfl", "cricket score",
    "lottery", "dating advice", "girlfriend", "boyfriend", "marriage advice",
    "travel itinerary", "visa application", "hotel booking", "flight booking",
    "diet plan", "weight loss", "workout routine", "gym plan", "doctor visit",
    "medical advice", "symptom", "medicine dose", "politics", "election", "president",
    "prime minister", "stock tip", "crypto price prediction", "gambling", "tarot",
    "poem about", "write a poem", "joke", "bedtime story", "vlog", "makeup", "fashion tip",
    "gardening", "pet care", "dog training", "cat behavior", "travel tips", "sightseeing",
)

_WORD_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _contains(text: str, needle: str) -> bool:
    """Substring match with word boundaries for plain words."""
    if needle != needle.strip():
        return needle in text
    pattern = _WORD_BOUNDARY_CACHE.get(needle)
    if pattern is None:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])")
        _WORD_BOUNDARY_CACHE[needle] = pattern
    return pattern.search(text) is not None


def has_technical_signal(question: str) -> bool:
    text = f" {question.lower()} "
    return any(_contains(text, signal) for signal in _TECH_SIGNALS)


def is_clearly_off_topic(question: str) -> bool:
    text = f" {question.lower()} "
    off_topic = any(_contains(text, signal) for signal in _OFF_TOPIC_SIGNALS)
    return off_topic and not has_technical_signal(question)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    refusal: str | None = None


def evaluate_policy(question: str) -> PolicyDecision:
    """Decide whether to answer directly or return a polite refusal."""
    if is_clearly_off_topic(question):
        return PolicyDecision(allowed=False, refusal=REFUSAL_MESSAGE)
    return PolicyDecision(allowed=True)
