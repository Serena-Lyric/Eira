"""Unit tests for text chunker."""

import pytest
from app.domain.knowledge.chunker import DocumentChunker, Chunk


class TestDocumentChunker:
    def setup_method(self):
        self.chunker = DocumentChunker(
            chunk_size=500,
            chunk_overlap=80,
            min_chunk_size=80,
        )

    def test_empty_text(self):
        chunks = self.chunker.chunk("")
        assert len(chunks) == 0

    def test_short_text(self):
        # Must be > 80 tokens (min_chunk_size) to produce a chunk
        text = "这是测试文本用于验证分块器基本功能。" * 30
        chunks = self.chunker.chunk(text)
        assert len(chunks) >= 1
        assert chunks[0].index == 0

    def test_chunk_metadata(self):
        text = "这是一个足够长的测试文本。" * 20 + "需要足够多的内容才能产生至少一个合格的文本块。"
        chunks = self.chunker.chunk(text, base_metadata={"page": 1})
        for chunk in chunks:
            assert "page" in chunk.metadata
            assert "chunk_index" in chunk.metadata
            assert chunk.metadata["page"] == 1

    def test_chinese_text_chunking(self):
        """Chinese text with natural sentence boundaries."""
        text = (
            "西湖位于浙江省杭州市，是中国最著名的淡水湖之一。"
            "西湖以其秀丽的自然风光和丰富的文化底蕴而闻名。"
            "苏堤春晓是西湖十景之一，春季清晨漫步苏堤，欣赏桃红柳绿的美景。"
            "断桥残雪则是冬日西湖的著名景观。"
            "三潭印月是中秋之夜不可错过的美景。"
        ) * 20
        chunks = self.chunker.chunk(text)
        assert len(chunks) >= 1
        # All chunks should be reasonable sizes
        for chunk in chunks:
            assert chunk.token_count >= 1

    def test_paragraph_splitting(self):
        """Text with explicit paragraph breaks."""
        paras = []
        for i in range(20):
            para = f"第{i}段：" + "这是用来测试段落分割功能的文本内容。" * 10
            paras.append(para)
        text = "\n\n".join(paras)
        chunks = self.chunker.chunk(text)
        assert len(chunks) >= 1

    def test_min_chunk_filtering(self):
        """Very small chunks should be merged or filtered."""
        # Use a chunker with high min_chunk_size to test filtering
        strict_chunker = DocumentChunker(
            chunk_size=500,
            chunk_overlap=80,
            min_chunk_size=200,
        )
        text = "短文本。"
        chunks = strict_chunker.chunk(text)
        # Either 0 chunks (filtered) or 1 (if it's the only content)
        assert len(chunks) <= 1

    def test_chunk_indices_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        text = "第一段测试文本。" * 30 + "第二段测试文本。" * 30 + "第三段测试文本。" * 30
        chunks = self.chunker.chunk(text)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_token_count_accuracy(self):
        """Token count should be consistent with tiktoken."""
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        text = "你好世界！这是一个测试。" * 20
        chunks = self.chunker.chunk(text)
        for chunk in chunks:
            expected = len(enc.encode(chunk.text))
            assert abs(chunk.token_count - expected) <= 1  # minor variance acceptable
