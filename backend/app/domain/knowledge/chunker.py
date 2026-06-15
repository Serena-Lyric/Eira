"""Sliding-window text chunker with token counting.

Parameters:
    chunk_size: 500 tokens
    chunk_overlap: 80 tokens
    min_chunk_size: 80 tokens
    encoding: cl100k_base (used by text-embedding-3-small)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import tiktoken

# Default parameters
DEFAULT_CHUNK_SIZE = 500  # tokens
DEFAULT_CHUNK_OVERLAP = 80  # tokens
MIN_CHUNK_SIZE = 80  # tokens
ENCODING_NAME = "cl100k_base"

# Sentence boundary patterns for split prioritization
_SENTENCE_END = re.compile(r"[。！？.!?]\s*")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_NEWLINE = re.compile(r"\n")


@dataclass
class Chunk:
    """A single text chunk with metadata."""
    text: str
    index: int
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    """Sliding-window chunker using tiktoken for accurate token counting."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = MIN_CHUNK_SIZE,
        encoding_name: str = ENCODING_NAME,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.encoding_name = encoding_name
        self._enc = tiktoken.get_encoding(encoding_name)

    def _token_count(self, text: str) -> int:
        """Count tokens in text."""
        return len(self._enc.encode(text))

    def chunk(self, text: str, base_metadata: dict | None = None) -> list[Chunk]:
        """Split text into overlapping chunks, preferring sentence boundaries.

        Args:
            text: The full document text to split.
            base_metadata: Metadata to attach to each chunk.

        Returns:
            List of Chunk objects.
        """
        if base_metadata is None:
            base_metadata = {}

        # Step 1: Split by paragraphs
        paragraphs = _PARAGRAPH_SPLIT.split(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Step 2: Split long paragraphs into sentences
        sentences: list[str] = []
        for para in paragraphs:
            if self._token_count(para) <= self.chunk_size:
                sentences.append(para)
            else:
                # Split by newlines within paragraph
                sub = _NEWLINE.split(para)
                for s in sub:
                    s = s.strip()
                    if not s:
                        continue
                    if self._token_count(s) <= self.chunk_size:
                        sentences.append(s)
                    else:
                        # Split by sentence boundaries
                        parts = _SENTENCE_END.split(s)
                        merged = []
                        for part in parts:
                            part = part.strip()
                            if not part:
                                continue
                            merged.append(part)
                        sentences.extend(merged)

        # Step 3: Build sliding window chunks
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sent_tokens = self._token_count(sentence)

            # If a single sentence exceeds chunk_size, force-split by comma
            if sent_tokens > self.chunk_size:
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(Chunk(
                        text=chunk_text,
                        index=chunk_index,
                        token_count=current_tokens,
                        metadata={**base_metadata, "chunk_index": chunk_index},
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Force split long sentence
                sub_chunks = self._force_split(sentence)
                for sc in sub_chunks:
                    sc_tokens = self._token_count(sc)
                    if sc_tokens >= self.min_chunk_size:
                        chunks.append(Chunk(
                            text=sc,
                            index=chunk_index,
                            token_count=sc_tokens,
                            metadata={**base_metadata, "chunk_index": chunk_index},
                        ))
                        chunk_index += 1
                continue

            # Check if adding this sentence exceeds chunk_size
            if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                # Finalize current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    token_count=current_tokens,
                    metadata={**base_metadata, "chunk_index": chunk_index},
                ))
                chunk_index += 1

                # Start new chunk with overlap: keep last N tokens worth of sentences
                overlap_target = max(0, self.chunk_size - self.chunk_overlap)
                # Simple approach: keep sentences that fit within overlap window
                current_chunk = []
                current_tokens = 0
                # Re-add sentences from the end for overlap
                for prev_sent in reversed(current_chunk if current_chunk else [sentence]):
                    prev_tokens = self._token_count(prev_sent)
                    if current_tokens + prev_tokens <= self.chunk_overlap:
                        pass  # We handle overlap differently below

                # Actually, simpler overlap: just keep some trailing content
                # We'll truncate the chunk and keep the tail as overlap head
                if chunks:
                    last_chunk_text = chunks[-1].text
                    last_sents = last_chunk_text.split(" ")
                    overlap_sents: list[str] = []
                    overlap_toks = 0
                    for s in reversed(last_sents):
                        s_toks = self._token_count(s)
                        if overlap_toks + s_toks > self.chunk_overlap:
                            break
                        overlap_sents.insert(0, s)
                        overlap_toks += s_toks
                    current_chunk = overlap_sents
                    current_tokens = overlap_toks

            current_chunk.append(sentence)
            current_tokens += sent_tokens

        # Finalize last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if current_tokens >= self.min_chunk_size:
                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    token_count=current_tokens,
                    metadata={**base_metadata, "chunk_index": chunk_index},
                ))
                chunk_index += 1
            elif chunks and chunks[-1].token_count + current_tokens <= self.chunk_size:
                # Merge small trailing chunk into previous
                chunks[-1].text = chunks[-1].text + " " + chunk_text
                chunks[-1].token_count += current_tokens

        return chunks

    def _force_split(self, text: str) -> list[str]:
        """Force-split a long text by commas when it exceeds chunk_size."""
        # Try comma splits first
        parts = [p.strip() for p in text.split("，")]
        if not parts or len(parts) == 1:
            parts = [p.strip() for p in text.split(",")]

        result: list[str] = []
        current = ""
        current_tokens = 0

        for part in parts:
            part_tokens = self._token_count(part)
            if current_tokens + part_tokens > self.chunk_size:
                if current:
                    result.append(current)
                current = part
                current_tokens = part_tokens
                # If still too big, force character-level split
                if current_tokens > self.chunk_size:
                    # Fallback: split by character count (rough estimate)
                    chars_per_token = len(part) / max(part_tokens, 1)
                    chunk_chars = int(self.chunk_size * chars_per_token)
                    for i in range(0, len(part), chunk_chars):
                        sub = part[i:i + chunk_chars]
                        if len(sub.strip()) >= 10:
                            result.append(sub.strip())
                    current = ""
                    current_tokens = 0
            else:
                if current:
                    current += "，" + part
                else:
                    current = part
                current_tokens += part_tokens

        if current and self._token_count(current) >= self.min_chunk_size:
            result.append(current)

        return result
