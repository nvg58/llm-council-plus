"""Advisor and persona MCP tools."""

from __future__ import annotations

import json
from typing import Any

from ..client import CouncilClient
from ..stream_buffer import buffer_debate

VALID_PERSONA_IDS = (
    "skeptic, pragmatist, innovator, historian, ethicist, analyst, contrarian, "
    "strategist, humanist, risk-assessor, comedian, economist"
)


def register(server: Any, base_url: str) -> None:
    """Register advisor and persona management tools on the MCP server."""

    @server.tool(description=(
        "List all available advisor personas. Returns all 12 built-in personas with any "
        "user customizations applied. Each persona has: id, name, role, description, "
        "system_prompt, avatar_emoji, color, is_customized. "
        f"Persona IDs: {VALID_PERSONA_IDS}."
    ))
    async def list_personas() -> str:
        try:
            async with CouncilClient(base_url) as client:
                personas = await client.get_personas()
            return json.dumps(personas, indent=2)
        except Exception as exc:
            return f"Error listing personas: {exc}"

    @server.tool(description=(
        "Get a single advisor persona by ID. Returns full persona details including "
        f"system_prompt. Valid IDs: {VALID_PERSONA_IDS}."
    ))
    async def get_persona(persona_id: str) -> str:
        try:
            async with CouncilClient(base_url) as client:
                personas = await client.get_personas()
            match = next((p for p in personas if p["id"] == persona_id), None)
            if match is None:
                return f"Persona '{persona_id}' not found. Valid IDs: {VALID_PERSONA_IDS}."
            return json.dumps(match, indent=2)
        except Exception as exc:
            return f"Error fetching persona: {exc}"

    @server.tool(description=(
        "Update an advisor persona's fields. All fields are optional — only provided "
        "fields are changed; others keep their current values. Changes persist to disk "
        "and mark the persona as is_customized=true. "
        "Use reset_persona to restore the original defaults."
    ))
    async def update_persona(
        persona_id: str,
        name: str | None = None,
        role: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        avatar_emoji: str | None = None,
    ) -> str:
        fields: dict[str, str] = {}
        if name is not None:
            fields["name"] = name
        if role is not None:
            fields["role"] = role
        if description is not None:
            fields["description"] = description
        if system_prompt is not None:
            fields["system_prompt"] = system_prompt
        if avatar_emoji is not None:
            fields["avatar_emoji"] = avatar_emoji

        if not fields:
            return "No fields provided. Specify at least one of: name, role, description, system_prompt, avatar_emoji."

        try:
            async with CouncilClient(base_url) as client:
                updated = await client.update_persona(persona_id, **fields)
            return json.dumps(updated, indent=2)
        except Exception as exc:
            return f"Error updating persona '{persona_id}': {exc}"

    @server.tool(description=(
        "Reset an advisor persona to its factory defaults, removing all customizations. "
        "Returns the restored default persona. Only works for personas that have been "
        "previously customized (is_customized=true)."
    ))
    async def reset_persona(persona_id: str) -> str:
        try:
            async with CouncilClient(base_url) as client:
                restored = await client.reset_persona(persona_id)
            return json.dumps(restored, indent=2)
        except Exception as exc:
            return f"Error resetting persona '{persona_id}': {exc}"

    @server.tool(description=(
        "Get the current advisor configuration: default model, tiebreaker model, "
        "temperature, and default round count. These are the global defaults used "
        "when run_advisor_debate does not specify per-persona model assignments."
    ))
    async def get_advisor_config() -> str:
        try:
            async with CouncilClient(base_url) as client:
                settings = await client.get_settings()
            config = {
                "advisor_default_model": settings.get("advisor_default_model", ""),
                "advisor_tiebreaker_model": settings.get("advisor_tiebreaker_model", ""),
                "advisor_temperature": settings.get("advisor_temperature", 0.7),
                "advisor_default_rounds": settings.get("advisor_default_rounds", 3),
            }
            return json.dumps(config, indent=2)
        except Exception as exc:
            return f"Error fetching advisor config: {exc}"

    @server.tool(description=(
        "Update advisor configuration. All fields are optional. "
        "default_model: model used for all advisor personas when no per-persona assignment is given. "
        "tiebreaker_model: model used for tiebreaker and verdict synthesis (falls back to default_model if empty). "
        "temperature: LLM temperature for advisor calls (0.0–2.0, default 0.7). "
        "default_rounds: default number of debate rounds (3–10, default 3)."
    ))
    async def configure_advisors(
        default_model: str | None = None,
        tiebreaker_model: str | None = None,
        temperature: float | None = None,
        default_rounds: int | None = None,
    ) -> str:
        updates: dict[str, Any] = {}
        if default_model is not None:
            updates["advisor_default_model"] = default_model
        if tiebreaker_model is not None:
            updates["advisor_tiebreaker_model"] = tiebreaker_model
        if temperature is not None:
            updates["advisor_temperature"] = temperature
        if default_rounds is not None:
            if not 3 <= default_rounds <= 10:
                return "Error: default_rounds must be between 3 and 10."
            updates["advisor_default_rounds"] = default_rounds

        if not updates:
            return "No fields provided. Specify at least one of: default_model, tiebreaker_model, temperature, default_rounds."

        try:
            async with CouncilClient(base_url) as client:
                current = await client.get_settings()
                current.update(updates)
                await client.update_settings(**current)
            lines = [f"  {k}: {v}" for k, v in updates.items()]
            return "Advisor config updated:\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error updating advisor config: {exc}"

    @server.tool(description=(
        "Run a multi-round advisor debate and return the full structured result. "
        "Automatically creates a new conversation and streams the debate to completion. "
        "Returns rounds of responses, the verdict, and optionally a tiebreaker. "
        "\n\n"
        "persona_ids: 2–4 persona IDs to participate. "
        f"Valid IDs: {VALID_PERSONA_IDS}. "
        "\n\n"
        "default_model: model for all advisors (uses saved advisor_default_model if omitted). "
        "model_assignments: per-persona model overrides, e.g. {\"skeptic\": \"openai:gpt-4.1\"}. "
        "max_rounds: number of debate rounds (3–10, default 3). "
        "search_provider: enable web search context — one of: duckduckgo, tavily, brave, serper, tinyfish. "
        "\n\n"
        "The result includes conversation_id so you can retrieve the full conversation later."
    ))
    async def run_advisor_debate(
        question: str,
        persona_ids: list[str],
        default_model: str | None = None,
        model_assignments: dict | None = None,
        max_rounds: int = 3,
        search_provider: str | None = None,
    ) -> str:
        if len(persona_ids) < 2:
            return "Error: at least 2 persona_ids are required."
        if len(persona_ids) > 4:
            return "Error: at most 4 persona_ids are supported."
        if not 3 <= max_rounds <= 10:
            return "Error: max_rounds must be between 3 and 10."

        try:
            async with CouncilClient(base_url) as client:
                conv = await client.create_conversation()
                conversation_id = conv["id"]
                events = client.stream_debate(
                    conversation_id=conversation_id,
                    question=question,
                    persona_ids=persona_ids,
                    default_model=default_model,
                    model_assignments=model_assignments,
                    max_rounds=max_rounds,
                    search_provider=search_provider,
                )
                result = await buffer_debate(events, conversation_id)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return json.dumps({
                "status": "error",
                "error": {"type": "network_error", "message": str(exc), "retryable": True},
            }, indent=2)
