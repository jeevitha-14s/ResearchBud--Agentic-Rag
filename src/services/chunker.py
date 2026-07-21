def chunk_text(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    text = text.strip()
    if not text:
        return []

    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_length = len(text)
    step = chunk_size - overlap

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]

        if end < text_length:
            paragraph_break = chunk.rfind("\n\n")
            if paragraph_break > chunk_size // 2:
                end = start + paragraph_break
                chunk = text[start:end]

        chunks.append((chunk.strip(), start, end))

        if end >= text_length:
            break
        start += step

    return chunks
