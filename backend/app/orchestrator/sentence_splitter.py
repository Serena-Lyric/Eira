"""Sentence splitter — breaks streaming LLM output into TTS-ready sentences.

Used by the voice pipeline to emit TTS audio sentence-by-sentence instead of
waiting for the full LLM response. This reduces end-to-end latency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Match action tags like [wave], [nod], [happy] etc.
_ACTION_TAG_RE = re.compile(r"\[[a-zA-Z_@]+\]")

# Sentence-ending delimiters (Chinese + English)
_SENTENCE_END_RE = re.compile(r"[。！？\n]")


@dataclass
class SentenceSplitter:
    """Splits streaming LLM text into complete sentences for TTS.

    Usage:
        splitter = SentenceSplitter(min_chars=6)
        for token in llm_stream:
            for sentence in splitter.feed(token):
                await tts_provider.stream(sentence)  # send to TTS
        for sentence in splitter.flush():
            await tts_provider.stream(sentence)  # send remaining
    """

    min_chars: int = 6
    delimiters: str = "。！？\n"

    # Internal state
    _buffer: str = field(default="", init=False, repr=False)

    @staticmethod
    def strip_action_tags(text: str) -> str:
        """Remove action tags like [wave], [nod], [happy] from display text."""
        return _ACTION_TAG_RE.sub("", text).strip()

    def feed(self, text: str) -> list[str]:
        """Feed incoming text, returning any complete sentences.

        Args:
            text: A chunk of text from the LLM stream.

        Returns:
            List of complete sentences ready for TTS synthesis.
        """
        if not text:
            return []

        self._buffer += text

        # Find sentence boundaries
        results: list[str] = []
        parts = _SENTENCE_END_RE.split(self._buffer)

        # All parts except the last are complete sentences (they were followed by a delimiter)
        # The last part is the beginning of the next sentence (incomplete)
        if len(parts) > 1:
            # Reconstruct sentences with their delimiters
            remaining = self._buffer
            for i, part in enumerate(parts[:-1]):
                # Find the delimiter that ended this sentence
                delim_match = _SENTENCE_END_RE.search(remaining)
                if delim_match:
                    delim = delim_match.group()
                    delim_pos = delim_match.start()
                    sentence = remaining[: delim_pos + len(delim)]
                    remaining = remaining[delim_pos + len(delim) :]

                    # Strip action tags and clean up
                    clean = self.strip_action_tags(sentence)
                    if clean and len(clean) >= self.min_chars:
                        results.append(clean)
                else:
                    break

            self._buffer = remaining.strip()
        else:
            # No delimiter found — buffer everything
            pass

        return results

    def flush(self) -> list[str]:
        """Return any remaining text in the buffer as a final sentence.

        Call this when the LLM stream ends to get the last incomplete sentence.
        """
        if not self._buffer or not self._buffer.strip():
            self._buffer = ""
            return []

        clean = self.strip_action_tags(self._buffer)
        self._buffer = ""
        if clean:
            return [clean]
        return []

    def reset(self) -> None:
        """Clear the buffer (e.g., on barge-in)."""
        self._buffer = ""
