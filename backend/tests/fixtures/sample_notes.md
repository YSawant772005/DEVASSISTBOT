# DevAssist sample notes (safe to distribute)

This is a small Markdown document used to demo Retrieval-Augmented Generation.
Upload it through the sidebar and ask a question about it.

## Retry policy

The DevAssist gateway retries a failed upstream request at most three times.
Each retry waits 250 milliseconds, and the backoff multiplies by two between
attempts. Requests that fail all three attempts return HTTP 503.

## Chunking defaults

Documents are split into chunks of 500 characters with an overlap of 50
characters. The retrieval step returns the three most relevant chunks.

## Embedding model

Embeddings are produced locally with the Sentence Transformers model
`sentence-transformers/all-MiniLM-L6-v2`, which yields 384-dimensional
vectors. Vectors are L2-normalized so inner-product search equals cosine
similarity.

## Sample Python snippet

```python
def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```
