"""Tests for deliberation MCP tools."""

import json
import pytest
import respx
import httpx
from llm_council_mcp.server import create_server


@pytest.fixture
def server():
    return create_server(base_url="http://test:8001")


def get_text(call_tool_result) -> str:
    """Extract plain text from call_tool's (content_blocks, raw) tuple."""
    content_blocks, _ = call_tool_result
    return content_blocks[0].text


def get_json(call_tool_result) -> dict:
    """Parse JSON from call_tool result."""
    return json.loads(get_text(call_tool_result))


# ── Helpers to build SSE bodies ────────────────────────────────────────────────

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _stage1_sse_body(models=None) -> str:
    """Minimal SSE body with stage1_complete."""
    if models is None:
        models = [
            {"model": "openai:gpt-4.1", "response": "Hello from GPT", "error": None},
            {"model": "anthropic:claude-sonnet-4", "response": "Hello from Claude", "error": None},
        ]
    return (
        _sse({"type": "stage1_start"})
        + _sse({"type": "stage1_complete", "data": models})
        + _sse({"type": "complete"})
    )


def _full_deliberation_sse_body() -> str:
    """Full SSE body: stage1 + stage2 + stage3."""
    stage1_models = [
        {"model": "openai:gpt-4.1", "response": "GPT answer", "error": None},
        {"model": "anthropic:claude-sonnet-4", "response": "Claude answer", "error": None},
    ]
    stage2_rankings = [
        {
            "model": "openai:gpt-4.1",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A",
            "parsed_ranking": ["Response B", "Response A"],
            "error": None,
        },
        {
            "model": "anthropic:claude-sonnet-4",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
            "error": None,
        },
    ]
    stage2_metadata = {
        "label_to_model": {
            "Response A": "openai:gpt-4.1",
            "Response B": "anthropic:claude-sonnet-4",
        },
        "aggregate_rankings": [
            {"model": "openai:gpt-4.1", "average_rank": 1.5, "rankings_count": 2},
            {"model": "anthropic:claude-sonnet-4", "average_rank": 1.5, "rankings_count": 2},
        ],
    }
    stage3_data = {
        "model": "anthropic:claude-opus-4",
        "response": "Synthesized final answer from the chairman.",
        "error": False,
    }
    return (
        _sse({"type": "stage1_start"})
        + _sse({"type": "stage1_complete", "data": stage1_models})
        + _sse({"type": "stage2_start"})
        + _sse({"type": "stage2_complete", "data": stage2_rankings, "metadata": stage2_metadata})
        + _sse({"type": "stage3_start"})
        + _sse({"type": "stage3_complete", "data": stage3_data})
        + _sse({"type": "complete"})
    )


def _stage1_plus_stage2_sse_body() -> str:
    """SSE body for chat_ranking mode: stage1 + stage2."""
    stage1_models = [
        {"model": "openai:gpt-4.1", "response": "GPT answer", "error": None},
        {"model": "anthropic:claude-sonnet-4", "response": "Claude answer", "error": None},
    ]
    stage2_rankings = [
        {
            "model": "openai:gpt-4.1",
            "ranking": "FINAL RANKING:\n1. Response B",
            "parsed_ranking": ["Response B"],
            "error": None,
        },
    ]
    stage2_metadata = {
        "label_to_model": {"Response B": "anthropic:claude-sonnet-4"},
        "aggregate_rankings": [
            {"model": "anthropic:claude-sonnet-4", "average_rank": 1.0, "rankings_count": 1},
        ],
    }
    return (
        _sse({"type": "stage1_start"})
        + _sse({"type": "stage1_complete", "data": stage1_models})
        + _sse({"type": "stage2_start"})
        + _sse({"type": "stage2_complete", "data": stage2_rankings, "metadata": stage2_metadata})
        + _sse({"type": "complete"})
    )


# ── run_stage1 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_stage1_creates_conversation_and_returns_results(server):
    """run_stage1 creates a new conversation and returns stage1 results."""
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-s1-1", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-s1-1/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_stage1_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage1", {"query": "What is 2+2?"})
        data = get_json(result)

    assert data["conversation_id"] == "conv-s1-1"
    assert data["query"] == "What is 2+2?"
    assert data["summary"]["total"] == 2
    assert data["summary"]["succeeded"] == 2
    assert data["summary"]["failed"] == 0
    assert len(data["results"]) == 2
    assert data["results"][0]["model"] == "openai:gpt-4.1"
    assert data["results"][0]["response"] == "Hello from GPT"
    assert data["results"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_run_stage1_uses_provided_conversation_id(server):
    """run_stage1 uses an existing conversation_id when provided."""
    with respx.mock:
        # Must NOT call create conversation
        respx.post(
            "http://test:8001/api/conversations/existing-conv/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_stage1_sse_body(models=[
                    {"model": "openai:gpt-4.1", "response": "Reused", "error": None},
                ]),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage1", {
            "query": "hello",
            "conversation_id": "existing-conv",
        })
        data = get_json(result)

    assert data["conversation_id"] == "existing-conv"
    assert data["results"][0]["response"] == "Reused"


@pytest.mark.asyncio
async def test_run_stage1_model_error(server):
    """run_stage1 correctly reports model-level errors."""
    error_body = _stage1_sse_body(models=[
        {"model": "openai:gpt-4.1", "response": "OK", "error": None},
        {"model": "groq:llama3", "response": None, "error": True, "error_message": "429 Too Many Requests"},
    ])
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-err", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-err/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=error_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage1", {"query": "test"})
        data = get_json(result)

    assert data["summary"]["succeeded"] == 1
    assert data["summary"]["failed"] == 1
    failed = next(r for r in data["results"] if r["status"] == "error")
    assert failed["error"]["type"] == "rate_limit"
    assert failed["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_run_stage1_web_search_flag(server):
    """run_stage1 with web_search=True includes search context in result."""
    search_body = (
        _sse({"type": "search_complete", "data": {"search_context": "web results", "search_query": "What is 2+2?"}})
        + _sse({"type": "stage1_complete", "data": [
            {"model": "openai:gpt-4.1", "response": "4", "error": None},
        ]})
        + _sse({"type": "complete"})
    )
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-ws", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-ws/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=search_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage1", {
            "query": "What is 2+2?",
            "web_search": True,
        })
        data = get_json(result)

    assert data["web_search"] is True
    assert data["search_context"] == "web results"


# ── run_stage2 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_stage2_returns_rankings(server):
    """run_stage2 drains stage1 events and returns stage2 rankings."""
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-s2", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-s2/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_stage1_plus_stage2_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage2", {"query": "Explain quantum computing"})
        data = get_json(result)

    assert data["conversation_id"] == "conv-s2"
    assert "rankings" in data
    assert "aggregate_rankings" in data
    assert "label_to_model" in data
    assert len(data["rankings"]) == 1
    assert data["rankings"][0]["model"] == "openai:gpt-4.1"
    assert data["rankings"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_run_stage2_uses_provided_conversation_id(server):
    """run_stage2 uses provided conversation_id without creating a new one."""
    with respx.mock:
        respx.post(
            "http://test:8001/api/conversations/existing-s2/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_stage1_plus_stage2_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage2", {
            "query": "test query",
            "conversation_id": "existing-s2",
        })
        data = get_json(result)

    assert data["conversation_id"] == "existing-s2"


# ── run_stage3 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_stage3_returns_synthesis(server):
    """run_stage3 drains stage1/2 and returns stage3 synthesis."""
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-s3", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-s3/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_full_deliberation_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage3", {"query": "What is consciousness?"})
        data = get_json(result)

    assert data["conversation_id"] == "conv-s3"
    assert data["status"] == "success"
    assert data["synthesis"] == "Synthesized final answer from the chairman."
    assert data["chairman_model"] == "anthropic:claude-opus-4"


@pytest.mark.asyncio
async def test_run_stage3_uses_provided_conversation_id(server):
    """run_stage3 uses provided conversation_id."""
    with respx.mock:
        respx.post(
            "http://test:8001/api/conversations/existing-s3/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_full_deliberation_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_stage3", {
            "query": "test",
            "conversation_id": "existing-s3",
        })
        data = get_json(result)

    assert data["conversation_id"] == "existing-s3"


# ── run_deliberation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_deliberation_returns_all_stages(server):
    """run_deliberation returns stage1, stage2, stage3, and chairman_answer."""
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-full", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-full/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_full_deliberation_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await server.call_tool("run_deliberation", {
            "query": "What is the best programming language?"
        })
        data = get_json(result)

    assert data["conversation_id"] == "conv-full"
    assert data["query"] == "What is the best programming language?"
    # Stage 1
    assert "stage1" in data
    assert data["stage1"]["summary"]["total"] == 2
    assert data["stage1"]["summary"]["succeeded"] == 2
    # Stage 2
    assert "stage2" in data
    assert len(data["stage2"]["rankings"]) == 2
    assert "aggregate_rankings" in data["stage2"]
    # Stage 3
    assert "stage3" in data
    assert data["stage3"]["status"] == "success"
    assert data["stage3"]["synthesis"] == "Synthesized final answer from the chairman."
    # Top-level shortcut
    assert data["chairman_answer"] == "Synthesized final answer from the chairman."


@pytest.mark.asyncio
async def test_run_deliberation_model_override_and_restore(server):
    """run_deliberation overrides council models and restores them afterward."""
    settings_response = {
        "council_models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"],
        "chairman_model": "anthropic:claude-opus-4",
    }
    put_calls = []

    def capture_put(request):
        body = json.loads(request.content)
        put_calls.append(body)
        return httpx.Response(200, json={"success": True})

    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json=settings_response)
        )
        respx.put("http://test:8001/api/settings").mock(side_effect=capture_put)
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-override", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-override/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_full_deliberation_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )

        override_models = ["groq:llama3-70b-8192", "ollama:llama3"]
        result = await server.call_tool("run_deliberation", {
            "query": "test",
            "models": override_models,
        })
        data = get_json(result)

    # Should have made 2 PUT calls: one to set overrides, one to restore
    assert len(put_calls) == 2
    # First PUT sets the override models
    assert put_calls[0]["council_models"] == override_models
    # Second PUT restores originals
    assert put_calls[1]["council_models"] == settings_response["council_models"]
    # Result is valid
    assert data["chairman_answer"] == "Synthesized final answer from the chairman."


@pytest.mark.asyncio
async def test_run_deliberation_model_override_restored_on_exception(server):
    """run_deliberation restores original models even when an exception occurs."""
    settings_response = {
        "council_models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"],
    }
    put_calls = []

    def capture_put(request):
        body = json.loads(request.content)
        put_calls.append(body)
        return httpx.Response(200, json={"success": True})

    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json=settings_response)
        )
        respx.put("http://test:8001/api/settings").mock(side_effect=capture_put)
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-exc", "title": ""})
        )
        # Simulate stream failure
        respx.post(
            "http://test:8001/api/conversations/conv-exc/message/stream"
        ).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(Exception):
            await server.call_tool("run_deliberation", {
                "query": "test",
                "models": ["groq:llama3-70b-8192", "ollama:llama3"],
            })

    # PUT calls: first sets override, second restores (even after exception)
    assert len(put_calls) == 2
    assert put_calls[0]["council_models"] == ["groq:llama3-70b-8192", "ollama:llama3"]
    assert put_calls[1]["council_models"] == settings_response["council_models"]


@pytest.mark.asyncio
async def test_run_deliberation_no_model_override_skips_settings(server):
    """run_deliberation without models= should not touch settings."""
    with respx.mock:
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-nomod", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-nomod/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=_full_deliberation_sse_body(),
                headers={"content-type": "text/event-stream"},
            )
        )
        # No GET or PUT settings mock — should not be called
        result = await server.call_tool("run_deliberation", {"query": "test"})
        data = get_json(result)

    assert data["chairman_answer"] is not None


# ── quick_chat ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quick_chat_returns_single_model_response(server):
    """quick_chat returns just the first model's response."""
    settings = {
        "council_models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"],
        "chairman_model": "anthropic:claude-opus-4",
    }
    put_calls = []

    def capture_put(request):
        body = json.loads(request.content)
        put_calls.append(body)
        return httpx.Response(200, json={"success": True})

    single_model_body = _stage1_sse_body(models=[
        {"model": "openai:gpt-4.1", "response": "Quick answer from GPT", "error": None},
        # Backend may echo the model twice since we set council_models=[model, model]
        {"model": "openai:gpt-4.1", "response": "Quick answer from GPT again", "error": None},
    ])

    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json=settings)
        )
        respx.put("http://test:8001/api/settings").mock(side_effect=capture_put)
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-qc", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-qc/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=single_model_body,
                headers={"content-type": "text/event-stream"},
            )
        )

        result = await server.call_tool("quick_chat", {
            "query": "What time is it?",
            "model": "openai:gpt-4.1",
        })
        data = get_json(result)

    # Returns single model's response (first result)
    assert data["model"] == "openai:gpt-4.1"
    assert data["response"] == "Quick answer from GPT"
    assert data["status"] == "success"
    assert data.get("error") is None

    # Settings were overridden and then restored
    assert len(put_calls) == 2
    # Override: model duplicated, chairman set
    assert put_calls[0]["council_models"] == ["openai:gpt-4.1", "openai:gpt-4.1"]
    assert put_calls[0]["chairman_model"] == "openai:gpt-4.1"
    # Restore: original settings
    assert put_calls[1]["council_models"] == settings["council_models"]
    assert put_calls[1]["chairman_model"] == settings["chairman_model"]


@pytest.mark.asyncio
async def test_quick_chat_restores_settings_on_error(server):
    """quick_chat restores original settings even when the stream fails."""
    settings = {
        "council_models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"],
        "chairman_model": "anthropic:claude-opus-4",
    }
    put_calls = []

    def capture_put(request):
        body = json.loads(request.content)
        put_calls.append(body)
        return httpx.Response(200, json={"success": True})

    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json=settings)
        )
        respx.put("http://test:8001/api/settings").mock(side_effect=capture_put)
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-qc-err", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-qc-err/message/stream"
        ).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(Exception):
            await server.call_tool("quick_chat", {
                "query": "test",
                "model": "openai:gpt-4.1",
            })

    # Restore PUT was still called despite the exception
    assert len(put_calls) == 2
    assert put_calls[1]["council_models"] == settings["council_models"]
    assert put_calls[1]["chairman_model"] == settings["chairman_model"]


@pytest.mark.asyncio
async def test_quick_chat_no_results_returns_error_json(server):
    """quick_chat returns an error JSON when no model results are returned."""
    empty_body = (
        _sse({"type": "stage1_complete", "data": []})
        + _sse({"type": "complete"})
    )
    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={
                "council_models": ["openai:gpt-4.1"],
                "chairman_model": "openai:gpt-4.1",
            })
        )
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        respx.post("http://test:8001/api/conversations").mock(
            return_value=httpx.Response(201, json={"id": "conv-empty", "title": ""})
        )
        respx.post(
            "http://test:8001/api/conversations/conv-empty/message/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                text=empty_body,
                headers={"content-type": "text/event-stream"},
            )
        )

        result = await server.call_tool("quick_chat", {
            "query": "test",
            "model": "openai:gpt-4.1",
        })
        data = get_json(result)

    assert "error" in data
    assert data["error"] == "No response received."
