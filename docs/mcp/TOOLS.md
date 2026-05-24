# MCP Tools Reference

The LLM Council Plus MCP server exposes **25 tools** grouped into five categories. Your AI assistant calls these automatically based on what you ask it to do — you rarely need to specify a tool name directly.

---

## Category Map

- **[Council Management](#council-management)**: `list_models`, `get_council_config`, `configure_council`, `set_search_provider`, `set_api_key`, `export_config`, `import_config`, `reset_config`
- **[Deliberation](#deliberation)**: `run_stage1`, `run_stage2`, `run_stage3`, `run_deliberation`, `quick_chat`, `chat`
- **[Advisor & Persona Management](#advisor--persona-management)**: `list_personas`, `get_persona`, `update_persona`, `reset_persona`, `get_advisor_config`, `configure_advisors`, `run_advisor_debate`
- **[Conversation Management](#conversation-management)**: `list_conversations`, `get_conversation`
- **[Health](#health)**: `check_health`, `test_provider`

---

## Council Management

### `list_models`
Lists all models available from all configured providers.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "What models are available in my council?"

**Example response:**
```json
{
  "models": [
    {"id": "openrouter:anthropic/claude-3.5-sonnet", "provider": "openrouter", "name": "Claude 3.5 Sonnet"},
    {"id": "ollama:granite4:1b", "provider": "ollama", "name": "granite4:1b"},
    {"id": "groq:llama3-70b-8192", "provider": "groq", "name": "Llama 3 70B"}
  ],
  "total": 3
}
```

---

### `get_council_config`
Returns the current council configuration: selected models, chairman, temperatures, and execution mode.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "What's my current council setup?"

**Example response:**
```json
{
  "council_members": ["openrouter:anthropic/claude-3.5-sonnet", "openai:gpt-4.1"],
  "chairman": "ollama:granite4:1b",
  "stage1_temperature": 0.5,
  "stage2_temperature": 0.3,
  "stage3_temperature": 0.4,
  "execution_mode": "full"
}
```

---

### `configure_council`
Updates council members, chairman, temperatures, or execution mode.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `models` | array of strings | No | 1–8 model IDs for the council |
| `chairman` | string | No | Model ID for the chairman |
| `stage1_temperature` | float (0.0–2.0) | No | Stage 1 creativity level |
| `stage2_temperature` | float (0.0–2.0) | No | Stage 2 ranking consistency |
| `stage3_temperature` | float (0.0–2.0) | No | Stage 3 synthesis creativity |
| `execution_mode` | string | No | `chat_only`, `chat_ranking`, or `full` |

**Example prompt:** "Set up a coding council with GPT-4.1 and Claude Sonnet, using full deliberation mode."

**Example response:**
```json
{
  "success": true,
  "config": {
    "council_members": ["openai:gpt-4.1", "openrouter:anthropic/claude-3.5-sonnet"],
    "execution_mode": "full"
  }
}
```

---

### `set_search_provider`
Sets the active web search provider.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | Yes | `duckduckgo`, `tavily`, `brave`, `serper`, or `tinyfish` |

**Example prompt:** "Switch my search provider to Tavily."

**Example response:**
```json
{"success": true, "provider": "tavily"}
```

---

### `set_api_key`
Sets the API key for a specified provider. Changes persist to settings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | Yes | `openrouter`, `openai`, `anthropic`, `google`, `mistral`, `deepseek`, `groq`, `tinyfish`, `tavily`, `brave`, `serper` |
| `api_key` | string | Yes | The secret API key string to save |

**Example prompt:** "Set my Anthropic API key to sk-proj-123..."

**Example response:**
```json
"API key for 'anthropic' saved."
```

---

### `export_config`
Exports the full council and advisor configurations as a JSON string, including actual API key values. Perfect for backups.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "Export my configuration so I can back it up."

**Example response:**
```json
{
  "openrouter_api_key": "sk-or-v1-...",
  "council_models": ["openrouter:anthropic/claude-3.5-sonnet"],
  "chairman_model": "ollama:granite4:1b",
  "advisor_default_model": "custom:deepseek-v4-flash-free",
  "advisor_default_rounds": 3
}
```

---

### `import_config`
Imports and restores a full council and advisor configuration from a JSON string, replacing all current settings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config_json` | string | Yes | The raw JSON configuration string to restore |

**Example prompt:** "Restore my configuration from this JSON string: ..."

**Example response:**
```json
"Configuration imported successfully."
```

---

### `reset_config`
Factory resets all configurations, clearing all API keys, custom endpoints, model overrides, and customized system prompts. **Irreversible.**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "Factory reset all my council settings."

**Example response:**
```json
"Configuration reset to defaults."
```

---

## Deliberation

### `run_stage1`
Runs Stage 1: sends the query to all council members in parallel and collects individual responses.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The question or prompt |
| `web_search` | boolean | No | Enable web search context (default: false) |
| `conversation_id` | string | No | Attach to an existing conversation |

**Example prompt:** "Ask the council Stage 1: what are the main tradeoffs of event-driven architecture?"

**Example response:**
```json
{
  "conversation_id": "abc-123",
  "responses": [
    {"model": "openai:gpt-4.1", "label": "Response A", "content": "Event-driven architecture..."},
    {"model": "anthropic:claude-3.5-sonnet", "label": "Response B", "content": "The primary tradeoffs..."}
  ],
  "stage": "stage1_complete"
}
```

---

### `run_stage2`
Runs Stage 2: each council member anonymously ranks and reviews all Stage 1 responses. Must be called after `run_stage1` with the same `conversation_id`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Same query used in Stage 1 |
| `conversation_id` | string | Yes | Conversation ID from Stage 1 |

**Example prompt:** (Called automatically as part of a full deliberation flow)

**Example response:**
```json
{
  "conversation_id": "abc-123",
  "rankings": [
    {"model": "openai:gpt-4.1", "ranking": ["Response B", "Response A"]},
    {"model": "anthropic:claude-3.5-sonnet", "ranking": ["Response A", "Response B"]}
  ],
  "aggregate_scores": {"Response A": 1.5, "Response B": 1.5},
  "stage": "stage2_complete"
}
```

---

### `run_stage3`
Runs Stage 3: the chairman synthesizes a final answer using all Stage 1 responses, Stage 2 rankings, and any search context. Must be called after `run_stage2` with the same `conversation_id`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Same query used in Stages 1 and 2 |
| `conversation_id` | string | Yes | Conversation ID from earlier stages |

**Example prompt:** (Called automatically as part of a full deliberation flow)

**Example response:**
```json
{
  "conversation_id": "abc-123",
  "chairman_answer": "Event-driven architecture offers excellent scalability and decoupling...",
  "stage": "stage3_complete"
}
```

---

### `run_deliberation`
Runs the full 3-stage deliberation in a single call. This is the most common tool for end-to-end use. Per-request model overrides never modify global settings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The question or prompt |
| `web_search` | boolean | No | Enable web search context (default: false) |
| `models` | array of strings | No | Override council members for this run only (1+ models) |

**Example prompt:** "Ask the council: what are the pros and cons of microservices?"

**Example response:**
```json
{
  "conversation_id": "abc-123",
  "stage1_responses": [...],
  "stage2_rankings": [...],
  "chairman_answer": "Microservices offer independent deployability and team autonomy...",
  "title": "Microservices: Pros and Cons"
}
```

---

### `quick_chat`
Sends a query to a single model with no deliberation. Uses the one-shot `/api/ask` endpoint — no conversation state, no settings mutation. **Stateless**: each call is independent with no memory. For multi-turn, use `chat` instead.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The question or prompt |
| `model` | string | Yes | Model ID (e.g., `openai:gpt-4.1`) |
| `web_search` | boolean | No | Enable web search context (default: false) |

**Example prompt:** "Ask GPT-4.1 directly: what is the difference between REST and GraphQL?"

**Example response:**
```json
{
  "model": "openai:gpt-4.1",
  "response": "REST and GraphQL are both API paradigms, but they differ in...",
  "error": null,
  "web_search_used": false
}
```

---

### `chat`
Chat with a model in a multi-turn conversation. The model sees the full conversation history from prior turns, so follow-up questions work naturally. First call: omit `conversation_id` to start a new conversation. Subsequent calls: pass the `conversation_id` from the previous response to continue.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The question or follow-up |
| `model` | string | Yes | Model ID (e.g., `openai:gpt-4.1`) |
| `conversation_id` | string | No | Pass from previous response to continue conversation |
| `web_search` | boolean | No | Enable web search context (default: false) |

**Example prompt:** "Chat with Claude about quantum computing..."

**First call response:**
```json
{
  "conversation_id": "abc-123",
  "model": "anthropic:claude-3.5-sonnet",
  "response": "Quantum computing uses qubits that can exist in superposition...",
  "error": null,
  "web_search_used": false
}
```

---

## Advisor & Persona Management

### `list_personas`
Lists all available advisor personas (built-in + customized). Returns JSON descriptions including roles, emoji, and customization status.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "List all my advisor personas."

**Example response:**
```json
[
  {
    "id": "skeptic",
    "name": "The Skeptic",
    "role": "Critical Thinker",
    "description": "Challenges assumptions, demands evidence, and highlights potential failure modes.",
    "avatar_emoji": "🔍",
    "color": "#f43f5e",
    "is_customized": false
  },
  {
    "id": "pragmatist",
    "name": "The Pragmatist",
    "role": "Practical Advisor",
    "description": "Focuses on feasibility, execution, and real-world constraints.",
    "avatar_emoji": "🔧",
    "color": "#10b981",
    "is_customized": true
  }
]
```

---

### `get_persona`
Retrieves the full details of a specific advisor persona by ID, including its custom system prompt.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `persona_id` | string | Yes | Persona ID (e.g. `skeptic`, `pragmatist`, `innovator`) |

**Example prompt:** "Show details for the skeptic persona."

**Example response:**
```json
{
  "id": "skeptic",
  "name": "The Skeptic",
  "role": "Critical Thinker",
  "description": "Challenges assumptions, demands evidence, and highlights potential failure modes.",
  "system_prompt": "You are The Skeptic. Your role is to critically analyze any proposal...",
  "avatar_emoji": "🔍",
  "color": "#f43f5e",
  "is_customized": false
}
```

---

### `update_persona`
Modifies one or more fields of an advisor persona. All fields except `persona_id` are optional; only provided fields are updated. Customizations persist to disk.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `persona_id` | string | Yes | Persona ID to modify (e.g. `ethicist`) |
| `name` | string | No | New name for the persona |
| `role` | string | No | New sub-role description |
| `description` | string | No | New short description of behavior |
| `system_prompt`| string | No | Detailed system instructions for the LLM |
| `avatar_emoji` | string | No | A single emoji representing the persona |

**Example prompt:** "Change the Pragmatist's name to 'The Realist' and set its emoji to 🛠️"

**Example response:**
```json
{
  "id": "pragmatist",
  "name": "The Realist",
  "role": "Practical Advisor",
  "description": "Focuses on feasibility...",
  "avatar_emoji": "🛠️",
  "is_customized": true
}
```

---

### `reset_persona`
Resets a persona to its factory defaults, wiping out any customizations. Only applies to customized personas (`is_customized` is true).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `persona_id` | string | Yes | Persona ID to restore (e.g. `pragmatist`) |

**Example prompt:** "Reset my Pragmatist persona to defaults."

**Example response:**
```json
{
  "id": "pragmatist",
  "name": "The Pragmatist",
  "role": "Practical Advisor",
  "avatar_emoji": "🔧",
  "is_customized": false
}
```

---

### `get_advisor_config`
Retrieves current global Advisor settings: default model, tiebreaker model, temperature, and round count.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "What is my current Advisor setup?"

**Example response:**
```json
{
  "advisor_default_model": "custom:deepseek-v4-flash-free",
  "advisor_tiebreaker_model": "ollama:granite4:1b",
  "advisor_temperature": 0.7,
  "advisor_default_rounds": 3
}
```

---

### `configure_advisors`
Updates global Advisor settings. All fields are optional.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `default_model` | string | No | Default model used for all advisor personas |
| `tiebreaker_model`| string | No | Model used for tiebreaker rounds and verdict synthesis |
| `temperature` | float | No | Temperature for advisor responses (0.0–2.0) |
| `default_rounds` | integer | No | Default round count (3–10) |

**Example prompt:** "Configure advisors to use deepseek-v4-flash-free as default with 4 rounds."

**Example response:**
```json
Advisor config updated:
  advisor_default_model: custom:deepseek-v4-flash-free
  advisor_default_rounds: 4
```

---

### `run_advisor_debate`
Orchestrates a structured debate on a question among 2–4 advisor personas across configurable rounds. Creates a conversation, streams rounds of statements, performs tiebreakers if necessary, and returns a final structured verdict.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question` | string | Yes | The central topic or decision to debate |
| `persona_ids` | array of strings | Yes | 2 to 4 persona IDs to participate (e.g. `["skeptic", "strategist", "ethicist"]`) |
| `default_model` | string | No | Override default model for all participants |
| `model_assignments`| object | No | Per-persona model overrides, e.g. `{"skeptic": "groq:llama-3.1"}` |
| `max_rounds` | integer | No | Maximum rounds to run (3–10, default: 3) |
| `search_provider` | string | No | Enable search provider (`duckduckgo`, `tavily`, etc.) |

**Example prompt:** "Get The Skeptic and The Strategist to debate if we should switch to microservices."

**Example response:**
```json
{
  "conversation_id": "deb-789",
  "status": "completed",
  "rounds": [
    {
      "round": 1,
      "messages": [
        {"persona": "skeptic", "content": "Microservices introduce massive distributed systems headaches..."},
        {"persona": "strategist", "content": "But they allow independent scaling and faster time-to-market..."}
      ]
    }
  ],
  "verdict": {
    "summary": "A highly contested debate between risk mitigation and long-term leverage.",
    "verdict": "PROCEED WITH CAUTION. Start with a modular monolith first.",
    "action_plan": ["1. Map bounds", "2. Build microservices only when needed"]
  }
}
```

---

## Conversation Management

### `list_conversations`
Returns a list of saved conversations with titles, mode (council vs. advisors), and timestamps.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "Show my conversation history."

**Example response:**
```json
{
  "conversations": [
    {"id": "abc-123", "title": "Microservices: Pros and Cons", "mode": "council", "created_at": "2026-05-10T14:22:00Z"},
    {"id": "deb-789", "title": "Should we switch to microservices?", "mode": "advisors", "created_at": "2026-05-24T18:00:00Z"}
  ],
  "total": 2
}
```

---

### `get_conversation`
Retrieves the complete content of a specific conversation by ID, containing either all council stages or all advisor rounds and verdicts.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conversation_id` | string | Yes | The conversation ID to retrieve |

**Example prompt:** "Retrieve conversation deb-789."

**Example response:**
```json
{
  "id": "deb-789",
  "title": "Should we switch to microservices?",
  "mode": "advisors",
  "rounds": [...],
  "verdict": {...},
  "created_at": "2026-05-24T18:00:00Z"
}
```

---

## Health

### `check_health`
Checks whether the LLM Council Plus backend REST API is reachable and lists the configuration status of each provider.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| _(none)_ | | | |

**Example prompt:** "Check if the council backend is healthy."

**Example response:**
```json
{
  "status": "ok",
  "backend_url": "http://localhost:8001",
  "providers": {
    "openrouter": "configured",
    "custom": "configured",
    "ollama": "configured",
    "groq": "not_configured"
  },
  "council_members": ["custom:deepseek-v4-flash-free"],
  "chairman": "ollama:granite4:1b"
}
```

---

### `test_provider`
Tests connectivity to a specific provider. You can optionally supply an `api_key` to test credentials before writing them to settings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | Yes | Provider to test (e.g. `openrouter`, `custom`, `ollama`) |
| `api_key` | string | No | Optional API key to test |

**Example prompt:** "Test the custom OpenCode endpoint."

**Example response:**
```json
{
  "provider": "custom",
  "status": "ok",
  "models_available": 3,
  "latency_ms": 140
}
```

---

## Error Format

When a tool call fails, the response includes a structured error object:

```json
{
  "error": {
    "type": "rate_limit",
    "message": "429 Too Many Requests from OpenRouter",
    "retryable": true
  }
}
```

Error types: `rate_limit`, `auth_error`, `timeout`, `model_not_found`, `network_error`, `provider_error`.
