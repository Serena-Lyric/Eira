"""Unit tests for document parsers."""

import pytest
from pathlib import Path

from app.domain.knowledge.parsers import (
    EmptyTextError,
    get_parser,
    supported_mime_types,
)
# Import all parsers to trigger registry registration
import app.domain.knowledge.parsers.text  # noqa: F401
import app.domain.knowledge.parsers.markdown  # noqa: F401
import app.domain.knowledge.parsers.pdf  # noqa: F401
import app.domain.knowledge.parsers.docx  # noqa: F401
from app.domain.knowledge.parsers.text import TextParser
from app.domain.knowledge.parsers.markdown import MarkdownParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "docs"


class TestParserRegistry:
    def test_supported_mime_types(self):
        types = supported_mime_types()
        assert "text/plain" in types
        assert "application/pdf" in types
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in types

    def test_get_parser_text(self):
        parser_cls = get_parser("text/plain")
        assert parser_cls is not None

    def test_get_parser_unknown(self):
        assert get_parser("application/unknown") is None


class TestTextParser:
    @pytest.mark.asyncio
    async def test_parse_utf8(self):
        parser = TextParser()
        content = (
            "这是第一段测试内容，包含了足够多的中文字符以满足最小段落过滤要求。\n\n"
            "这是第二段测试内容，用来验证文本解析器的基本功能是否正常工作。\n\n"
            "这是第三段落的内容，提供了更多测试数据以确保解析的准确性。"
        )
        result = await parser.parse(content.encode("utf-8"), "test.txt")
        assert len(result.text) > 0
        assert result.page_count == 1
        assert result.metadata["filename"] == "test.txt"

    @pytest.mark.asyncio
    async def test_parse_empty(self):
        parser = TextParser()
        content = "短".encode("utf-8")  # Too short, < 20 chars
        with pytest.raises(EmptyTextError):
            await parser.parse(content, "empty.txt")

    @pytest.mark.asyncio
    async def test_parse_from_fixture(self):
        parser = TextParser()
        sample_path = FIXTURES / "sample.txt"
        content = sample_path.read_bytes()
        result = await parser.parse(content, sample_path.name)
        assert len(result.text) > 100
        assert "西湖" in result.text
        assert "杭州" in result.text

    @pytest.mark.asyncio
    async def test_parse_gbk_encoding(self):
        parser = TextParser()
        # Chinese text encoded in GBK — each line must be >= 20 chars
        text = (
            "这是GBK编码的测试文本内容，用于验证多编码解析功能。\n"
            "第二行内容足够长来通过最小段落过滤的检查测试。"
        )
        content = text.encode("gbk")
        result = await parser.parse(content, "gbk.txt")
        assert "GBK" in result.text or "编码" in result.text or "测试" in result.text


class TestMarkdownParser:
    @pytest.mark.asyncio
    async def test_parse_markdown(self):
        parser = MarkdownParser()
        md = """# 景区介绍

西湖是中国著名的淡水湖，位于浙江省杭州市。西湖以其秀丽的自然风光和丰富的文化底蕴而闻名。

## 主要景点

- 苏堤春晓：春季清晨漫步苏堤，欣赏桃红柳绿的美景。
- 三潭印月：中秋之夜，月光透过三座石塔倒映在湖水中。

详细内容请参考[西湖官网](https://example.com)。"""
        result = await parser.parse(md.encode("utf-8"), " guide.md")
        assert len(result.text) > 50
        assert "西湖" in result.text
        # Links should be stripped, keeping text
        assert "https://" not in result.text or "example.com" not in result.text

    @pytest.mark.asyncio
    async def test_parse_empty_markdown(self):
        parser = MarkdownParser()
        md = "# Title\n\nshort"
        with pytest.raises(EmptyTextError):
            await parser.parse(md.encode("utf-8"), "empty.md")


class TestPdfParser:
    @pytest.mark.asyncio
    async def test_parse_pdf_empty_bytes(self):
        """PDF parser raises EmptyTextError on non-PDF content."""
        from app.domain.knowledge.parsers.pdf import PdfParser
        parser = PdfParser()
        # Invalid PDF content
        with pytest.raises(Exception):  # pypdf raises various errors on invalid input
            await parser.parse(b"not a pdf file at all", "fake.pdf")
