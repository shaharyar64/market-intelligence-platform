"""Splits extracted document text into overlapping token-bounded chunks
before embedding. Token-counted with tiktoken (already a dependency of this
service via requirements-food.txt) rather than characters or words, so
chunk size tracks what the embedding model actually sees.
"""
import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str, chunk_tokens: int = 800, overlap_tokens: int = 100) -> list[str]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("chunk_text requires non-empty text")

    tokens = _ENCODING.encode(stripped)
    if len(tokens) <= chunk_tokens:
        return [stripped]

    words = stripped.split()
    if not words:
        return [stripped]

    # Convert overlap_tokens to word count. Use 0.72 words per token (realistic ratio for
    # cl100k_base on English prose), so overlap_tokens scales sensibly: small overlaps give
    # small word counts, and overlap_tokens near chunk_tokens gives substantial chunk overlap.
    overlap_words = max(1, round(overlap_tokens * 0.72))

    chunks = []
    word_idx = 0

    while word_idx < len(words):
        # Find the end of the current chunk by greedily adding words
        # until the token count would exceed the budget
        chunk_end = word_idx

        while chunk_end < len(words):
            test_chunk = " ".join(words[word_idx:chunk_end + 1])
            test_tokens = len(_ENCODING.encode(test_chunk))

            if test_tokens > chunk_tokens:
                break

            chunk_end += 1

        # Ensure we always have at least one word
        if chunk_end == word_idx:
            chunk_end = word_idx + 1

        # Extract and save the chunk
        chunk_text = " ".join(words[word_idx:chunk_end])
        chunks.append(chunk_text)

        # Move to next chunk position with word-level overlap
        # Guarantee forward progress: cap overlap so at least one new word is added.
        # This prevents hangs when chunk size is small relative to overlap.
        if chunk_end < len(words):
            max_overlap = max(0, chunk_end - word_idx - 1)
            actual_overlap = min(overlap_words, max_overlap)
            word_idx = chunk_end - actual_overlap
        else:
            break

    return chunks
