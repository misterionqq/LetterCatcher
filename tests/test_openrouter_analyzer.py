import json
import pytest
from aioresponses import aioresponses

from src.infrastructure.openrouter_client import OpenRouterAnalyzer

API_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def analyzer():
    return OpenRouterAnalyzer(api_key="test-key", model="test-model")


def _ok_response(is_important=True, reason="Test reason"):
    return {
        "choices": [{"message": {"content": json.dumps({
            "is_important": is_important,
            "reason": reason,
        })}}]
    }


async def test_successful_analysis(analyzer):
    with aioresponses() as m:
        m.post(API_URL, payload=_ok_response(True, "Deadline approaching"))

        result = await analyzer.analyze_urgency("Test", "body")

        assert result["is_important"] is True
        assert result["reason"] == "Deadline approaching"


async def test_json_in_markdown_fences(analyzer):
    content = '```json\n{"is_important": true, "reason": "Fenced"}\n```'
    response = {"choices": [{"message": {"content": content}}]}

    with aioresponses() as m:
        m.post(API_URL, payload=response)
        result = await analyzer.analyze_urgency("Test", "body")

        assert result["is_important"] is True
        assert result["reason"] == "Fenced"


async def test_invalid_json(analyzer):
    response = {"choices": [{"message": {"content": "not json at all"}}]}

    with aioresponses() as m:
        m.post(API_URL, payload=response)
        result = await analyzer.analyze_urgency("Test", "body")

        assert result["is_important"] is False


async def test_retry_on_500(analyzer):
    with aioresponses() as m:
        m.post(API_URL, status=500)
        m.post(API_URL, payload=_ok_response(True, "After retry"))

        result = await analyzer.analyze_urgency("Test", "body")

        assert result["is_important"] is True
        assert result["reason"] == "After retry"


async def test_all_retries_exhausted(analyzer):
    with aioresponses() as m:
        for _ in range(3):
            m.post(API_URL, status=500)

        result = await analyzer.analyze_urgency("Test", "body")

        assert result["is_important"] is False
        assert "недоступен" in result["reason"]


async def test_text_truncation(analyzer):
    long_body = "x" * 3000

    with aioresponses() as m:
        m.post(API_URL, payload=_ok_response())

        result = await analyzer.analyze_urgency("Subject", long_body)

        # Verify the call succeeds and the prompt contains truncated text
        assert result["is_important"] is True
        # Inspect the actual request payload sent
        request_keys = list(m.requests.keys())
        assert len(request_keys) == 1
        sent = m.requests[request_keys[0]][0].kwargs["json"]
        prompt_text = sent["messages"][0]["content"]
        # The full 3000-char body should NOT appear in the prompt (truncated to 1500)
        assert "x" * 3000 not in prompt_text
        assert "x" * 1500 in prompt_text
