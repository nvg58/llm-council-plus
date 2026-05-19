---
name: llm-council-api
version: 0.5.0
description: Use when interacting with LLM Council Plus via HTTP API — configuring the council or advisors, running deliberations or persona debates, managing personas, or inspecting conversations — especially when the MCP server is unavailable, the SSE session is stale, or direct REST access is preferred. Triggers on requests like "ask the council", "run an advisor debate", "configure models", "list personas", "edit a persona", "run a deliberation", "check council health", or any manipulation of the LLM Council Plus system.
---

# LLM Council Plus — HTTP API Skill

## Overview

LLM Council Plus has two operating modes:

- **Council mode** — 3-stage multi-LLM deliberation: individual responses → anonymous peer ranking → chairman synthesis
- **Advisor mode** — Named personas debate a question across configurable rounds, reaching consensus or delivering a structured verdict

This skill lets you control both modes entirely via the REST API — no MCP required. Use it when MCP is unavailable, the SSE session is stale, or you prefer direct API access.

**Default base URL:** `http://localhost:8001`  
**Remote server:** replace with `http://<server-ip>:8001`

---

## Quick Reference

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Health check | GET | `/api/health` |
| **One-shot query (no state)** | **POST** | **`/api/ask`** |
| Get settings (council + advisor config) | GET | `/api/settings` |
| Update settings | PUT | `/api/settings` |
| List all models | GET | `/api/models` + `/api/models/direct` + `/api/ollama/tags` + `/api/custom-endpoint/models` |
| List conversations | GET | `/api/conversations` |
| Create conversation | POST | `/api/conversations` |
| Get conversation | GET | `/api/conversations/{id}` |
| Send message (sync JSON) | POST | `/api/conversations/{id}/message` |
| Send message (SSE stream) | POST | `/api/conversations/{id}/message/stream` |
| **Run advisor debate (SSE stream)** | **POST** | **`/api/conversations/{id}/debate/stream`** |
| List all personas | GET | `/api/personas` |
| Update a persona | PATCH | `/api/personas/{id}` |
| Reset persona to defaults | DELETE | `/api/personas/{id}/override` |
| Test a provider | POST | `/api/settings/test-provider` |
| Export settings (backup) | GET | `/api/settings/export` |
| Import settings (restore) | POST | `/api/settings/import` |
| Reset settings to defaults | POST | `/api/settings/reset` |

**Model ID prefix format:**
```
openrouter:anthropic/claude-sonnet-4   → Cloud via OpenRouter
ollama:llama3.1:latest                 → Local Ollama
anthropic:claude-sonnet-4              → Direct Anthropic API
openai:gpt-4.1                         → Direct OpenAI API
custom:nvidia/nemotron-3-super-120b    → Custom endpoint
groq:llama3-70b-8192                   → Groq fast inference
```

---

## Choosing the Right Endpoint

| Scenario | Endpoint | Why |
|----------|----------|-----|
| One-shot query, no history needed | `POST /api/ask` | Simplest path. One call, JSON response, no state. |
| One-shot query with web search | `POST /api/ask` with `web_search: true` | Same simplicity, adds search context. |
| Full deliberation, don't need live progress | `POST /api/ask` with `execution_mode: "full"` | Returns all stages in one JSON response. |
| Multi-turn conversation with follow-ups | `POST /api/conversations/{id}/message` | Models see full prior context. JSON response. |
| Multi-turn with live SSE progress | `POST /api/conversations/{id}/message/stream` | Real-time stage updates + multi-turn context. |
| **Persona-driven debate** | **`POST /api/conversations/{id}/debate/stream`** | Named advisors argue across rounds; returns verdict. |

**Key principles:**
- Never mutate global config for ad-hoc queries. Use per-request `models` / `council_models` / `chairman_model` overrides instead.
- Use conversation endpoints when you need follow-up questions — models automatically receive prior turns as context.
- `/api/ask` is stateless — no memory between calls.
- Advisor debates always require a conversation — create one first, then stream the debate to it.

---

## Examples

### 1. One-Shot Query (Recommended for Scripts/MCPs)

The simplest way to query a model. No conversation, no state, no cleanup.

```bash
curl -X POST http://localhost:8001/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "content": "What is the capital of France?",
    "models": ["custom:moonshotai/kimi-k2.6"],
    "execution_mode": "chat_only"
  }'
# → {"response": "The capital of France is Paris.", "model": "custom:moonshotai/kimi-k2.6", "error": null}
```

```python
import httpx

async def ask(query, model, web_search=False, base_url="http://localhost:8001"):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{base_url}/api/ask", json={
            "content": query,
            "models": [model],
            "web_search": web_search,
            "execution_mode": "chat_only",
        })
        return r.json()["response"]

# Usage:
# answer = await ask("Explain quantum tunneling", "openai:gpt-4.1")
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | — | The question/prompt |
| `models` | array of strings | No | Global council config | 1+ model IDs to query |
| `chairman_model` | string | No | Global chairman config | Override chairman for `full` mode |
| `web_search` | boolean | No | `false` | Enable web search context |
| `execution_mode` | string | No | `"chat_only"` | `chat_only`, `chat_ranking`, or `full` |

**Response shapes by mode:**

- **`chat_only` + 1 model:** `{"response": "...", "model": "...", "error": null}`
- **`chat_only` + N models:** `{"responses": [{model, response, error}, ...]}`
- **`chat_ranking`:** `{"responses": [...], "rankings": [...], "aggregate_rankings": [...], "label_to_model": {...}}`
- **`full`:** `{"response": "...", "chairman_model": "...", "responses": [...], "rankings": [...], "aggregate_rankings": [...], "label_to_model": {...}}`

---

### 2. One-Shot with Multiple Models

```bash
curl -X POST http://localhost:8001/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Compare REST vs GraphQL",
    "models": ["openai:gpt-4.1", "anthropic:claude-sonnet-4", "custom:moonshotai/kimi-k2.6"],
    "execution_mode": "chat_only"
  }'
# → {"responses": [{model, response, error}, {model, response, error}, ...]}
```

---

### 3. One-Shot Full Deliberation

```python
async def deliberate(query, models, base_url="http://localhost:8001"):
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{base_url}/api/ask", json={
            "content": query,
            "models": models,
            "execution_mode": "full",
            "web_search": True,
        })
        data = r.json()
        return data["response"]  # Chairman's synthesized answer
```

No conversation management. No config mutation. One call.

---

### 4. Streaming with Per-Request Overrides (for UIs/MCPs needing live progress)

When you need SSE events for real-time progress (stage1_progress, stage2_progress, etc.), use the streaming endpoint with per-request model overrides:

```python
import asyncio, httpx, json

async def stream_deliberation(query, models, chairman=None, web_search=False, base_url="http://localhost:8001"):
    async with httpx.AsyncClient(timeout=300) as client:
        # Create conversation (only needed for stream endpoint)
        conv = (await client.post(f"{base_url}/api/conversations", json={})).json()
        conv_id = conv["id"]

        # Stream with per-request overrides — global config untouched
        payload = {
            "content": query,
            "web_search": web_search,
            "execution_mode": "full",
            "council_models": models,        # per-request override
            "chairman_model": chairman,       # per-request override
        }

        stage3 = {}
        async with client.stream("POST", f"{base_url}/api/conversations/{conv_id}/message/stream", json=payload) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                t = event.get("type")
                if t == "stage3_complete":
                    stage3 = event["data"]

        return stage3.get("response")
```

**Per-request override fields (available on both `/message` and `/message/stream`):**

| Field | Type | Description |
|-------|------|-------------|
| `council_models` | array of strings | Override which models run in Stage 1+2 |
| `chairman_model` | string | Override which model runs Stage 3 synthesis |

These fields are optional. If omitted, the global config is used. They **never mutate** settings.

---

### 5. Multi-Turn Conversations (Follow-Up Questions)

Conversation endpoints automatically pass prior turns as context to the models. The models see the full chat history, so follow-up questions work naturally.

```python
import httpx

async def multi_turn_chat(base_url="http://localhost:8001"):
    async with httpx.AsyncClient(timeout=120) as client:
        # Create conversation once
        conv = (await client.post(f"{base_url}/api/conversations", json={})).json()
        conv_id = conv["id"]

        # First question
        r1 = await client.post(f"{base_url}/api/conversations/{conv_id}/message", json={
            "content": "What is a monad in functional programming?",
            "execution_mode": "chat_only",
            "council_models": ["openai:gpt-4.1"],
        })
        print("A1:", r1.json()["stage1"][0]["response"])

        # Follow-up — the model remembers the previous exchange
        r2 = await client.post(f"{base_url}/api/conversations/{conv_id}/message", json={
            "content": "Can you give me a concrete example in Python?",
            "execution_mode": "chat_only",
            "council_models": ["openai:gpt-4.1"],
        })
        print("A2:", r2.json()["stage1"][0]["response"])

        # Third turn — full context of turns 1+2 is available
        r3 = await client.post(f"{base_url}/api/conversations/{conv_id}/message", json={
            "content": "How does this compare to Rust's Result type?",
            "execution_mode": "chat_only",
            "council_models": ["openai:gpt-4.1"],
        })
        print("A3:", r3.json()["stage1"][0]["response"])
```

**How context works:**
- Each message sent to a conversation endpoint includes all prior user/assistant turns as chat history
- For assistant context, the system uses the chairman synthesis (stage3) when available, otherwise the first successful model response from stage1
- `/api/ask` is stateless — no multi-turn memory (use conversations for that)
- You can reuse the same `conversation_id` across sessions — history is persisted to disk

**When to use multi-turn vs one-shot:**

| Scenario | Endpoint | Multi-turn? |
|----------|----------|-------------|
| Independent questions, no follow-up needed | `POST /api/ask` | No |
| Research session with follow-ups | `POST /api/conversations/{id}/message` | Yes |
| Interactive exploration with live progress | `POST /api/conversations/{id}/message/stream` | Yes |

---

### 6. Sync Conversation Endpoint (JSON, saves to history)

For when you want conversation history but don't need SSE streaming:

```bash
# Create conversation first
CONV_ID=$(curl -s -X POST http://localhost:8001/api/conversations -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Send message (returns JSON, saves to conversation)
curl -X POST "http://localhost:8001/api/conversations/$CONV_ID/message" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Explain monads in simple terms",
    "execution_mode": "chat_only",
    "council_models": ["openai:gpt-4.1"]
  }'
```

Response includes all stages that were executed:
```json
{
  "stage1": [{"model": "openai:gpt-4.1", "response": "...", "error": null}],
  "stage2": null,
  "stage3": null,
  "aggregate_rankings": null,
  "label_to_model": null
}
```

---

### 7. Health Check

```bash
curl http://localhost:8001/api/health
# → {"status": "ok", "service": "LLM Council API"}
```

---

### 8. Get Current Council Configuration

```bash
curl http://localhost:8001/api/settings | python3 -m json.tool
```

Key fields returned:
- `council_models` — list of model IDs in the council
- `chairman_model` — model that synthesizes the final answer
- `execution_mode` — `"full"` / `"chat_ranking"` / `"chat_only"`
- `search_provider` — active search provider
- `*_api_key_set` — boolean flags (never returns actual keys)
- `custom_endpoint_name` / `custom_endpoint_url` — custom provider details

---

### 9. Update Global Council Configuration

```bash
curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "council_models": ["custom:z-ai/glm-5.1", "ollama:granite4.1:8b", "custom:moonshotai/kimi-k2.6"],
    "chairman_model": "custom:nvidia/nemotron-3-super-120b-a12b",
    "execution_mode": "full"
  }'
```

All fields are optional — only provided fields are updated. Requires minimum 1 model.

**Valid `execution_mode` values:**
- `"full"` — all 3 stages (individual → peer review → chairman synthesis)
- `"chat_ranking"` — stages 1+2 (no chairman synthesis)
- `"chat_only"` — stage 1 only (fastest, individual responses)

---

### 10. Configure System Prompts and Provider Toggles

```bash
curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "stage1_prompt": "You are an expert analyst. Answer with evidence and cite sources.",
    "stage2_prompt": "Rank the responses below by accuracy and depth.",
    "stage3_prompt": "Synthesize the best elements from all responses into a definitive answer."
  }'

curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "enabled_providers": {"openrouter": true, "ollama": false, "groq": true, "direct": false},
    "direct_provider_toggles": {"openai": true, "anthropic": true, "google": false}
  }'
```

**`enabled_providers` keys:** `openrouter`, `ollama`, `groq`, `direct` (master toggle for all direct), `custom`  
**`direct_provider_toggles` keys:** `openai`, `anthropic`, `google`, `mistral`, `deepseek`, `groq`

---

### 11. Set API Keys

```bash
curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"openrouter_api_key": "sk-or-...", "openai_api_key": "sk-..."}'
```

| Provider | Field name |
|----------|-----------|
| OpenRouter | `openrouter_api_key` |
| OpenAI | `openai_api_key` |
| Anthropic | `anthropic_api_key` |
| Google | `google_api_key` |
| Mistral | `mistral_api_key` |
| DeepSeek | `deepseek_api_key` |
| Groq | `groq_api_key` |
| TinyFish | `tinyfish_api_key` |
| Tavily | `tavily_api_key` |
| Brave | `brave_api_key` |
| Serper | `serper_api_key` |

Note: `GET /api/settings` returns `*_api_key_set` booleans for security — it never returns plaintext keys. `GET /api/settings/export` does return plaintext keys but is admin-gated: it only accepts requests from loopback, or from callers presenting `Authorization: Bearer $LLM_COUNCIL_ADMIN_TOKEN` when that env var is set. Do not invoke `/api/settings/export` automatically on behalf of a user; treat it as a manual administrative action.

Security/admin environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_COUNCIL_ADMIN_TOKEN` | unset | Enables remote access to settings export/import/reset when callers send `Authorization: Bearer <token>`. If unset, these admin endpoints accept only direct loopback clients and reject proxied external clients. |
| `LLM_COUNCIL_BIND_HOST` | `127.0.0.1` | Local dev launcher bind host for `python -m backend.main`. Set to `0.0.0.0` for intentional LAN access. |
| `LLM_COUNCIL_BIND_PORT` | `8001` | Local dev launcher bind port for `python -m backend.main`. |

---

### 12. List All Available Models

```python
import asyncio, httpx

async def list_all_models(base_url="http://localhost:8001"):
    async with httpx.AsyncClient(timeout=30) as client:
        results = []
        for endpoint in ["/api/models", "/api/models/direct", 
                         "/api/ollama/tags", "/api/custom-endpoint/models"]:
            try:
                r = await client.get(f"{base_url}{endpoint}")
                if r.status_code == 200:
                    results.extend(r.json().get("models", []))
            except Exception:
                pass
    return results

models = asyncio.run(list_all_models())
for m in models[:10]:
    print(m.get("id"), "—", m.get("name"))
```

---

### 13. Retrieve a Past Conversation

```python
async def get_conversation(conv_id, base_url="http://localhost:8001"):
    async with httpx.AsyncClient() as client:
        conv = (await client.get(f"{base_url}/api/conversations/{conv_id}")).json()
    for msg in conv.get("messages", []):
        if msg["role"] == "user":
            print("Q:", msg["content"])
        elif msg["role"] == "assistant":
            s3 = msg.get("stage3", {})
            if s3:
                print("A (chairman):", s3.get("response", "")[:500])
    return conv
```

---

### 14. List and Inspect Personas

```bash
# List all 10 personas with current customizations
curl http://localhost:8001/api/personas | python3 -m json.tool

# Each persona has: id, name, role, description, system_prompt, avatar_emoji, color, is_customized
```

```python
import httpx

async def get_persona(persona_id, base_url="http://localhost:8001"):
    async with httpx.AsyncClient() as client:
        personas = (await client.get(f"{base_url}/api/personas")).json()
    return next((p for p in personas if p["id"] == persona_id), None)
```

**Built-in persona IDs:** `skeptic`, `pragmatist`, `innovator`, `historian`, `ethicist`, `analyst`, `contrarian`, `strategist`, `humanist`, `risk-assessor`

---

### 15. Update a Persona

Customize any persona's name, role, description, system prompt, or emoji. Changes persist to disk and mark `is_customized: true`.

```bash
curl -X PATCH http://localhost:8001/api/personas/skeptic \
  -H "Content-Type: application/json" \
  -d '{
    "name": "The Devil'"'"'s Advocate",
    "role": "Adversarial Thinker",
    "system_prompt": "You are The Devil'"'"'s Advocate. Your role is to challenge every claim aggressively, find the weakest link in any argument, and force other advisors to defend their positions rigorously."
  }'
# → Returns the updated persona object with is_customized: true
```

Only provided fields are changed; others keep their current values.

**To reset a persona to its factory defaults:**

```bash
curl -X DELETE http://localhost:8001/api/personas/skeptic/override
# → Returns the restored default persona with is_customized: false
```

---

### 16. Run an Advisor Debate

Personas debate your question across configurable rounds, then a neutral model produces a verdict.

```python
import asyncio, httpx, json

async def run_advisor_debate(
    question: str,
    persona_ids: list[str],           # 2-4 required
    default_model: str,
    max_rounds: int = 2,
    search_provider: str | None = None,
    base_url: str = "http://localhost:8001",
) -> dict:
    async with httpx.AsyncClient(timeout=300) as client:
        # Create a fresh conversation to hold the debate
        conv = (await client.post(f"{base_url}/api/conversations", json={})).json()
        conv_id = conv["id"]

        payload = {
            "question": question,
            "persona_ids": persona_ids,
            "default_model": default_model,
            "max_rounds": max_rounds,
            "web_search": search_provider is not None,
            "search_provider": search_provider,
        }

        result = {}
        async with client.stream("POST", f"{base_url}/api/conversations/{conv_id}/debate/stream", json=payload) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "advisor_complete":
                    result = event["data"]
                    result["conversation_id"] = conv_id

        return result

# Usage
result = asyncio.run(run_advisor_debate(
    question="Should we rewrite this service in Rust?",
    persona_ids=["skeptic", "pragmatist", "innovator"],
    default_model="openai:gpt-4.1",
    max_rounds=2,
))
print("Consensus:", result["consensus_reached"])
print("Verdict:", result["verdict"]["content"])
```

**Debate request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question` | string | Yes | — | The topic to debate |
| `persona_ids` | array | Yes | — | 2–4 persona IDs |
| `default_model` | string | No | `advisor_default_model` setting | Model for all advisors |
| `model_assignments` | object | No | — | Per-persona overrides: `{"skeptic": "openai:gpt-4.1"}` |
| `max_rounds` | integer | No | `advisor_default_rounds` setting | Number of rounds (1–10) |
| `web_search` | boolean | No | `false` | Enable web search context |
| `search_provider` | string | No | — | `duckduckgo`, `tavily`, `brave`, `serper`, `tinyfish` |

**`advisor_complete` event data:**

```json
{
  "rounds": [
    {
      "round_number": 1,
      "responses": [
        {"persona_id": "skeptic", "persona_name": "The Skeptic", "model": "openai:gpt-4.1",
         "content": "I question whether Rust's learning curve justifies the rewrite..."}
      ]
    }
  ],
  "consensus_reached": false,
  "tiebreaker": null,
  "verdict": {
    "model": "openai:gpt-4.1",
    "content": "## Summary\n\nThe debate highlighted...\n\n## Verdict\n\nA targeted rewrite...",
    "error": null
  },
  "personas": [...]
}
```

---

### 17. Advisor Debate with Per-Persona Models and Web Search

```python
result = asyncio.run(run_advisor_debate(
    question="What is the best architecture for a real-time data pipeline?",
    persona_ids=["analyst", "innovator", "pragmatist", "risk-assessor"],
    default_model="openai:gpt-4.1",
    max_rounds=3,
    search_provider="duckduckgo",
))

# Access individual round responses
for round_data in result["rounds"]:
    print(f"\n--- Round {round_data['round_number']} ---")
    for resp in round_data["responses"]:
        print(f"{resp['persona_name']}: {resp['content'][:200]}...")

print("\n=== VERDICT ===")
print(result["verdict"]["content"])
```

**To assign different models per persona:**

```bash
curl -X POST "http://localhost:8001/api/conversations/$CONV_ID/debate/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Monolith vs microservices for a 5-person startup?",
    "persona_ids": ["skeptic", "pragmatist", "innovator"],
    "model_assignments": {
      "skeptic": "anthropic:claude-sonnet-4-6",
      "pragmatist": "openai:gpt-4.1",
      "innovator": "custom:moonshotai/kimi-k2.6"
    },
    "max_rounds": 2
  }'
```

---

### 18. Configure Advisor Settings

```bash
# Set default model and round count for advisor debates
curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "advisor_default_model": "openai:gpt-4.1",
    "advisor_tiebreaker_model": "anthropic:claude-sonnet-4-6",
    "advisor_temperature": 0.7,
    "advisor_default_rounds": 2
  }'
```

**Advisor settings fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `advisor_default_model` | `""` | Model for all advisors when no per-persona assignment given |
| `advisor_tiebreaker_model` | `""` | Model for tiebreaker + verdict synthesis (falls back to `advisor_default_model`) |
| `advisor_temperature` | `0.7` | LLM temperature for advisor calls |
| `advisor_default_rounds` | `2` | Default number of debate rounds (1–10) |

---

## Backup and Restore

```bash
# Export full settings from the backend host itself (includes actual API key values)
curl http://localhost:8001/api/settings/export -o council-settings.json

# Remote export requires LLM_COUNCIL_ADMIN_TOKEN on the server
curl -H "Authorization: Bearer $LLM_COUNCIL_ADMIN_TOKEN" \
  http://SERVER:8001/api/settings/export -o council-settings.json

# Import settings from backup locally, or add the same Authorization header remotely
curl -X POST http://localhost:8001/api/settings/import \
  -H "Content-Type: application/json" \
  -d @council-settings.json

# Reset all settings to factory defaults locally, or add the same Authorization header remotely
curl -X POST http://localhost:8001/api/settings/reset
```

---

## Search Provider Configuration

```bash
# Switch to TinyFish (free, 5 req/min)
curl -X PUT http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"search_provider": "tinyfish", "tinyfish_api_key": "sk-tinyfish-..."}'

# Valid providers: duckduckgo, tavily, brave, serper, tinyfish
# duckduckgo requires no key; all others require an API key
```

---

## Key SSE Event Types

### Council streaming (`/message/stream`)

| Event | When | Contains |
|-------|------|----------|
| `search_start` | Web search begins | `provider` |
| `search_complete` | After web search | `search_context`, `search_query` |
| `stage1_init` | Before Stage 1 responses | `total` (model count) |
| `stage1_progress` | Each model responds | `data`: `{model, response, error}`, `count`, `total` |
| `stage1_complete` | After all models respond | `data`: list of `{model, response, error}` |
| `stage2_init` | Before Stage 2 rankings | `total` |
| `stage2_progress` | Each model ranks | `data`: `{model, ranking, parsed_ranking}`, `count`, `total` |
| `stage2_complete` | After peer review | `metadata`: `{label_to_model, aggregate_rankings}` |
| `stage3_complete` | After chairman synthesis | `data`: `{model, response, error}` |
| `title_complete` | Title generated | `data`: `{title}` |
| `error` | On failure | `message` |
| `complete` | Stream finished | — |

### Advisor debate streaming (`/debate/stream`)

| Event | When | Contains |
|-------|------|----------|
| `advisor_search_start` | Web search begins | — |
| `advisor_search_complete` | After web search | `data`: `{search_query}` |
| `advisor_debate_start` | Debate initialized | `data`: `{personas, max_rounds, question, web_search}` |
| `advisor_round_start` | Each round begins | `data`: `{round_number, order, is_parallel}` |
| `advisor_response` | Each persona responds | `data`: `{persona_id, persona_name, model, content, error, consensus}`, `round`, `count`, `total` |
| `advisor_round_complete` | Round finishes | `data`: `{round_number, responses, consensus_votes, consensus_reached}` |
| `advisor_tiebreaker_start` | Tiebreaker triggered (2 personas, no consensus) | — |
| `advisor_tiebreaker` | Tiebreaker result | `data`: `{model, content, error}` |
| `advisor_verdict_start` | Verdict generation begins | — |
| `advisor_verdict` | Verdict result | `data`: `{model, content, error}` |
| `advisor_complete` | **Authoritative final event** | `data`: `{rounds, consensus_reached, verdict, tiebreaker, personas}` |
| `advisor_error` | Debate failed | `message` |
| `title_complete` | Title generated (first message only) | `data`: `{title}` |

**Important:** Always prefer `advisor_complete` as the authoritative source. Earlier per-event data is provisional accumulation; `advisor_complete` contains the final cleaned result used for persistence.

---

## Error Handling

Model errors appear inside stage results — not as top-level failures:

```python
for model_result in stage1:
    if model_result.get("error"):
        msg = model_result.get("error_message", "unknown error")
        if "429" in msg:
            print(f"{model_result['model']}: rate limited — retryable")
        elif "401" in msg or "403" in msg:
            print(f"{model_result['model']}: auth error — check API key")
        else:
            print(f"{model_result['model']}: failed — {msg}")
    else:
        print(f"{model_result['model']}: responded")
```

The `/api/ask` endpoint returns HTTP 502 if ALL models fail, with error details in the response body.

The council continues with successful models even if some fail.

---

## Troubleshooting

**Backend unreachable (`ConnectionRefused`)**
- Local: verify `uv run python -m backend.main` is running on port 8001
- Remote: check `http://<server>:8001/api/health` is accessible; firewall may be blocking port 8001
- Docker: run `docker ps` to confirm container is up and healthy

**Council models not updating**
- PUT to `/api/settings` returns the full settings object — check `council_models` in the response
- Model IDs must include provider prefix (e.g., `custom:z-ai/glm-5.1`, not `z-ai/glm-5.1`)

**SSE stream hangs or times out**
- Use `timeout=300` on the httpx client for full deliberations (can take 60-120 seconds)
- Check backend logs for provider-side errors
- Consider using `POST /api/ask` instead — no streaming complexity

**Model returns error in Stage 1**
- Check `*_api_key_set` flags in `/api/settings` — key may be missing
- Test a specific provider: `POST /api/settings/test-provider` with `{"provider_id": "openai", "api_key": "sk-..."}`
- Custom endpoint models need `custom_endpoint_url` and `custom_endpoint_api_key` configured

**Settings not persisting after restart**
- Settings are stored in `data/settings.json` — if using Docker, confirm the `./data` volume is mounted

---

## Installation

**Option 1: Clone and symlink**
```bash
git clone https://github.com/jacob-bd/llm-council-plus.git
mkdir -p ~/.claude/skills
ln -s "$(pwd)/llm-council-plus/skills/llm-council-api" ~/.claude/skills/llm-council-api
```

**Option 2: Copy directly**
```bash
mkdir -p ~/.claude/skills/llm-council-api
curl -o ~/.claude/skills/llm-council-api/SKILL.md \
  https://raw.githubusercontent.com/jacob-bd/llm-council-plus/main/skills/llm-council-api/SKILL.md
```

After installation, Claude Code automatically discovers and loads the skill when you ask about council operations.
