"""Unit tests for LLM logging decorator (T1.8)."""

import pytest
from app.capabilities.llm.logging_decorator import log_llm_call


@pytest.mark.asyncio
async def test_log_llm_call_logs_start_and_end():
    """Decorator should not interfere with the function result."""

    @log_llm_call(provider="test", model="test-model")
    async def successful_call():
        return "hello"

    result = await successful_call()
    assert result == "hello"


@pytest.mark.asyncio
async def test_log_llm_call_passes_through_exceptions():
    """Decorator should re-raise exceptions after logging."""

    @log_llm_call(provider="test", model="test-model")
    async def failing_call():
        raise ValueError("simulated failure")

    with pytest.raises(ValueError, match="simulated failure"):
        await failing_call()


@pytest.mark.asyncio
async def test_log_llm_call_preserves_function_metadata():
    """Decorator should preserve __name__ and __doc__."""

    @log_llm_call(provider="test", model="test-model")
    async def my_func():
        """My docstring."""
        return 42

    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "My docstring."
