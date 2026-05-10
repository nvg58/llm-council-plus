"""Tests for council management MCP tools."""

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


@pytest.mark.asyncio
async def test_list_models_returns_model_info(server):
    with respx.mock:
        respx.get("http://test:8001/api/models").mock(
            return_value=httpx.Response(200, json={"models": [
                {
                    "id": "openrouter:openai/gpt-4.1",
                    "name": "GPT-4.1",
                    "provider": "OpenRouter",
                    "is_free": False,
                }
            ]})
        )
        respx.get("http://test:8001/api/models/direct").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        respx.get("http://test:8001/api/ollama/tags").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        respx.get("http://test:8001/api/custom-endpoint/models").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        result = await server.call_tool("list_models", {})
        text = get_text(result)
        assert "GPT-4.1" in text
        assert "OpenRouter" in text
        assert "Found 1 models" in text


@pytest.mark.asyncio
async def test_list_models_free_flag(server):
    with respx.mock:
        respx.get("http://test:8001/api/models").mock(
            return_value=httpx.Response(200, json={"models": [
                {
                    "id": "openrouter:meta-llama/llama-3-8b-instruct:free",
                    "name": "Llama 3 8B",
                    "provider": "OpenRouter",
                    "is_free": True,
                }
            ]})
        )
        respx.get("http://test:8001/api/models/direct").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        respx.get("http://test:8001/api/ollama/tags").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        respx.get("http://test:8001/api/custom-endpoint/models").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        result = await server.call_tool("list_models", {})
        text = get_text(result)
        assert "(free)" in text


@pytest.mark.asyncio
async def test_list_models_empty(server):
    with respx.mock:
        for url in [
            "http://test:8001/api/models",
            "http://test:8001/api/models/direct",
            "http://test:8001/api/ollama/tags",
            "http://test:8001/api/custom-endpoint/models",
        ]:
            respx.get(url).mock(return_value=httpx.Response(200, json={"models": []}))
        result = await server.call_tool("list_models", {})
        text = get_text(result)
        assert "No models available" in text


@pytest.mark.asyncio
async def test_get_council_config(server):
    with respx.mock:
        respx.get("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={
                "council_models": ["openai:gpt-4.1"],
                "chairman_model": "anthropic:claude-sonnet-4",
                "council_temperature": 0.5,
                "chairman_temperature": 0.4,
                "stage2_temperature": 0.3,
                "execution_mode": "full",
                "search_provider": "duckduckgo",
            })
        )
        result = await server.call_tool("get_council_config", {})
        text = get_text(result)
        assert "council_models" in text
        assert "chairman_model" in text
        assert "openai:gpt-4.1" in text
        assert "anthropic:claude-sonnet-4" in text
        assert "duckduckgo" in text


@pytest.mark.asyncio
async def test_configure_council_too_few_models(server):
    result = await server.call_tool("configure_council", {"models": ["openai:gpt-4.1"]})
    text = get_text(result)
    assert "Error" in text
    assert "2-8" in text


@pytest.mark.asyncio
async def test_configure_council_too_many_models(server):
    models = [f"openai:model-{i}" for i in range(9)]
    result = await server.call_tool("configure_council", {"models": models})
    text = get_text(result)
    assert "Error" in text
    assert "2-8" in text


@pytest.mark.asyncio
async def test_configure_council_invalid_mode(server):
    result = await server.call_tool("configure_council", {"execution_mode": "invalid"})
    text = get_text(result)
    assert "Error" in text


@pytest.mark.asyncio
async def test_configure_council_no_args(server):
    result = await server.call_tool("configure_council", {})
    text = get_text(result)
    assert "No changes requested" in text


@pytest.mark.asyncio
async def test_configure_council_success(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("configure_council", {
            "models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"],
            "chairman": "anthropic:claude-opus-4",
            "execution_mode": "full",
        })
        text = get_text(result)
        assert "Council updated successfully" in text
        assert "openai:gpt-4.1" in text
        assert "full" in text


@pytest.mark.asyncio
async def test_configure_council_temperatures_only(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("configure_council", {
            "council_temperature": 0.7,
            "chairman_temperature": 0.3,
        })
        text = get_text(result)
        assert "Council updated successfully" in text


@pytest.mark.asyncio
async def test_set_search_provider_invalid(server):
    result = await server.call_tool("set_search_provider", {"provider": "notreal"})
    text = get_text(result)
    assert "Error" in text
    assert "notreal" in text


@pytest.mark.asyncio
async def test_set_search_provider_duckduckgo(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("set_search_provider", {"provider": "duckduckgo"})
        text = get_text(result)
        assert "duckduckgo" in text
        assert "Error" not in text


@pytest.mark.asyncio
async def test_set_search_provider_tinyfish_with_key(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("set_search_provider", {
            "provider": "tinyfish",
            "api_key": "tf-key-abc123",
        })
        text = get_text(result)
        assert "tinyfish" in text
        assert "API key saved" in text


@pytest.mark.asyncio
async def test_set_search_provider_valid_options(server):
    """All valid provider names should succeed (mocked backend)."""
    valid_providers = ("duckduckgo", "tavily", "brave", "serper", "tinyfish")
    for provider in valid_providers:
        with respx.mock:
            respx.put("http://test:8001/api/settings").mock(
                return_value=httpx.Response(200, json={"success": True})
            )
            result = await server.call_tool("set_search_provider", {"provider": provider})
            text = get_text(result)
            assert "Error" not in text, f"Provider '{provider}' should be valid but got: {text}"


# ── Extended configure_council tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_configure_council_with_stage1_prompt(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("configure_council", {
            "stage1_prompt": "You are a helpful expert council member.",
        })
        text = get_text(result)
        assert "Council updated successfully" in text


@pytest.mark.asyncio
async def test_configure_council_with_enabled_providers(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("configure_council", {
            "enabled_providers": {"openrouter": True, "ollama": False},
        })
        text = get_text(result)
        assert "Council updated successfully" in text


# ── set_api_key tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_api_key_valid_provider(server):
    with respx.mock:
        respx.put("http://test:8001/api/settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await server.call_tool("set_api_key", {
            "provider": "openai",
            "api_key": "sk-test-key",
        })
        text = get_text(result)
        assert "openai" in text
        assert "saved" in text


@pytest.mark.asyncio
async def test_set_api_key_invalid_provider(server):
    result = await server.call_tool("set_api_key", {"provider": "notreal", "api_key": "x"})
    text = get_text(result)
    assert "Error" in text
    assert "notreal" in text


# ── export_config tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_config(server):
    with respx.mock:
        respx.get("http://test:8001/api/settings/export").mock(
            return_value=httpx.Response(200, json={
                "council_models": ["openai:gpt-4.1"],
                "openai_api_key": "sk-real-key",
            })
        )
        result = await server.call_tool("export_config", {})
        text = get_text(result)
        assert "council_models" in text
        assert "openai_api_key" in text


# ── import_config tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_config_valid(server):
    import json
    with respx.mock:
        respx.post("http://test:8001/api/settings/import").mock(
            return_value=httpx.Response(200, json={"status": "imported"})
        )
        config = json.dumps({"council_models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4"]})
        result = await server.call_tool("import_config", {"config_json": config})
        text = get_text(result)
        assert "imported" in text.lower()


@pytest.mark.asyncio
async def test_import_config_invalid_json(server):
    result = await server.call_tool("import_config", {"config_json": "not-json{"})
    text = get_text(result)
    assert "Error" in text


# ── reset_config tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_config(server):
    with respx.mock:
        respx.post("http://test:8001/api/settings/reset").mock(
            return_value=httpx.Response(200, json={"status": "reset"})
        )
        result = await server.call_tool("reset_config", {})
        text = get_text(result)
        assert "reset" in text.lower()
