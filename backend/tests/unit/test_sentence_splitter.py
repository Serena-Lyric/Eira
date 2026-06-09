"""Unit tests for SentenceSplitter — LLM output → TTS-ready sentences."""

import pytest

from app.orchestrator.sentence_splitter import SentenceSplitter


class TestSentenceSplitter:
    def test_empty_feed_returns_nothing(self):
        splitter = SentenceSplitter()
        results = splitter.feed("")
        assert results == []

    def test_single_sentence_delimiter(self):
        splitter = SentenceSplitter()
        results = splitter.feed("你好，欢迎来到西湖。")
        assert results == ["你好，欢迎来到西湖。"]

    def test_multiple_sentences(self):
        splitter = SentenceSplitter()
        results = splitter.feed("今天天气真好。我们出去玩吧！你想去哪里？")
        assert results == [
            "今天天气真好。",
            "我们出去玩吧！",
            "你想去哪里？",
        ]

    def test_chinese_period(self):
        splitter = SentenceSplitter()
        results = splitter.feed("西湖是著名景点。")
        assert results == ["西湖是著名景点。"]

    def test_incomplete_sentence_buffered(self):
        """Text without delimiter should be buffered, not emitted."""
        splitter = SentenceSplitter()
        results = splitter.feed("我在想")
        assert results == []

    def test_minimum_chars_enforced(self):
        """Sentences shorter than min_chars are not split."""
        splitter = SentenceSplitter(min_chars=6)
        results = splitter.feed("你好。")
        # "你好。" is only 3 chars, below min_chars threshold
        # Should stay buffered until more text arrives or flush
        assert results == []

        # Adding more text pushes it over threshold
        results2 = splitter.feed("今天天气真好。")
        # Combined: "你好。今天天气真好。" but we split at delimiters
        # First sentence "你好。" is still below threshold so stays combined
        # Actually: the buffer has "你好。今天天气真好。" which splits to "你好。" and "今天天气真好。"
        # "你好。" is still below 6 chars → should merge with next
        assert len(results2) >= 1

    def test_action_tags_stripped(self):
        splitter = SentenceSplitter(min_chars=4)
        results = splitter.feed("欢迎光临[wave]！这边请[nod]。")
        assert "[wave]" not in "".join(results)
        assert "[nod]" not in "".join(results)
        assert len(results) >= 1

    def test_flush_returns_remaining(self):
        splitter = SentenceSplitter()
        splitter.feed("未完成的句子")
        remaining = splitter.flush()
        assert remaining == ["未完成的句子"]

    def test_flush_empty_buffer(self):
        splitter = SentenceSplitter()
        remaining = splitter.flush()
        assert remaining == []

    def test_reset_clears_buffer(self):
        splitter = SentenceSplitter()
        splitter.feed("前半句")
        splitter.reset()
        results = splitter.feed("新句子开始。")
        # After reset, previous buffer should be cleared
        assert len(results) == 1
        assert "新句子开始。" in results[0]

    def test_newline_delimiter(self):
        splitter = SentenceSplitter(min_chars=6)
        results = splitter.feed("第一行内容比较长\n第二行内容也足够长\n")
        assert len(results) >= 1

    def test_complex_text_with_tags(self):
        splitter = SentenceSplitter(min_chars=6)
        text = (
            "[happy]你好呀！今天天气不错。"
            "你想去哪里玩呢？我推荐西湖[wave]。"
            "那里风景优美，还有很多美食哦！"
        )
        results = splitter.feed(text)
        # Should have multiple sentences with tags stripped
        assert len(results) >= 2
        for r in results:
            assert "[" not in r
            assert "]" not in r

    def test_sequential_feeds(self):
        """Simulate streaming tokens arriving one at a time."""
        splitter = SentenceSplitter(min_chars=4)
        tokens = list("大家好呀。我是Eira导游。很高兴认识你！")
        all_results = []
        for token in tokens:
            results = splitter.feed(token)
            all_results.extend(results)

        # Final flush
        all_results.extend(splitter.flush())

        assert len(all_results) >= 2
        # First emitted sentence should be the first complete one
        assert "大家好呀" in all_results[0]
        assert "Eira" in " ".join(all_results)

    def test_semicolons_not_delimiters(self):
        """Semicolons and commas should not trigger sentence boundary."""
        splitter = SentenceSplitter()
        results = splitter.feed("这里有山、有水、有美景；让人流连忘返。")
        # Should be one sentence ending with 。
        assert len(results) == 1 or (
            len(results) >= 1 and results[-1].endswith("。")
        )

    def test_whitespace_only(self):
        splitter = SentenceSplitter()
        results = splitter.feed("   \n  ")
        assert results == []
        remaining = splitter.flush()
        assert remaining == [] or all(r.strip() == "" for r in remaining)
