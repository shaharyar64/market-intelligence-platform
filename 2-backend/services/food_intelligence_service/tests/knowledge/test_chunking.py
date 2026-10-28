from services.food_intelligence_service.app.knowledge.chunking import chunk_text


def test_chunk_text_returns_one_chunk_for_short_text():
    chunks = chunk_text("A short concept brief about a rooftop amenity.")
    assert chunks == ["A short concept brief about a rooftop amenity."]


def test_chunk_text_splits_long_text_into_multiple_chunks():
    # ~3000 words, well over the 800-token default chunk size.
    long_text = " ".join(f"word{i}" for i in range(3000))
    chunks = chunk_text(long_text, chunk_tokens=800, overlap_tokens=100)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_chunks_overlap():
    long_text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(long_text, chunk_tokens=800, overlap_tokens=100)
    words0 = chunks[0].strip().split()
    words1 = chunks[1].strip().split()
    max_check = min(len(words0), len(words1))
    overlap = 0
    for n in range(1, max_check + 1):
        if words0[-n:] == words1[:n]:
            overlap = n
    assert overlap >= 50


def test_chunk_text_rejects_empty_input():
    import pytest
    with pytest.raises(ValueError):
        chunk_text("   ")


def test_chunk_text_drops_lines_repeated_on_many_pages():
    pages = [f"Finding {i} about juice\n©S ixthF a ctor Cons ulting , 2022" for i in range(12)]
    pages[0] += "\n©InsightFactor Consulting, 2022"
    chunks = chunk_text("\n".join(pages))
    assert "Consulting" not in " ".join(chunks).replace(" ", "")
    assert "Finding 11 about juice" in chunks[-1]
