"""LLM Advisors debate orchestrator."""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional

from .council import query_model
from .personas import get_persona, get_personas_by_ids, Persona
from .settings import get_settings
from .advisor_prompts import (
    ADVISOR_ROUND1_PROMPT,
    ADVISOR_FOLLOWUP_PROMPT,
    ADVISOR_VERDICT_PROMPT,
    ADVISOR_TIEBREAKER_PROMPT,
    CONSENSUS_TAG_INSTRUCTION,
)

logger = logging.getLogger(__name__)


def parse_consensus_tag(content: str) -> bool:
    """Extract CONSENSUS:YES or CONSENSUS:NO from end of response."""
    if not content:
        return False
    match = re.search(r"CONSENSUS:(YES|NO)\s*$", content.strip(), re.IGNORECASE)
    if match:
        return match.group(1).upper() == "YES"
    return False


def strip_consensus_tag(content: str) -> str:
    """Remove the CONSENSUS tag from the response for display."""
    if not content:
        return content
    return re.sub(r"\n*CONSENSUS:(YES|NO)\s*$", "", content.strip(), flags=re.IGNORECASE).strip()


def build_rotation_order(persona_ids: List[str], round_number: int) -> List[str]:
    """Rotate speaking order for each round. Round 1 = original order, Round 2 = shift left by 1, etc."""
    n = len(persona_ids)
    shift = (round_number - 1) % n
    return persona_ids[shift:] + persona_ids[:shift]


def _format_transcript(rounds: List[Dict[str, Any]], personas: Dict[str, Persona]) -> str:
    """Format the debate transcript for injection into prompts."""
    lines = []
    for r in rounds:
        lines.append(f"--- Round {r['round_number']} ---")
        for resp in r["responses"]:
            p = personas.get(resp["persona_id"])
            name = p.name if p else resp["persona_id"]
            role = p.role if p else ""
            lines.append(f"\n{name} ({role}):\n{resp['content']}")
    return "\n".join(lines)


def _resolve_model(
    persona_id: str,
    model_assignments: Optional[Dict[str, str]],
    default_model: str,
) -> str:
    """Determine which model to use for a given persona."""
    if model_assignments and persona_id in model_assignments:
        return model_assignments[persona_id]
    return default_model


async def run_debate(
    question: str,
    persona_ids: List[str],
    model_assignments: Optional[Dict[str, str]] = None,
    default_model: Optional[str] = None,
    max_rounds: int = 2,
    web_search: bool = False,
    search_context: str = "",
    request: Any = None,
):
    """
    Run a multi-round advisor debate.

    Async generator yielding SSE-compatible event dicts.

    Args:
        question: The question to debate
        persona_ids: List of persona IDs to participate (2-4)
        model_assignments: Optional per-persona model mapping
        default_model: Fallback model for all personas
        max_rounds: Maximum debate rounds (1-10)
        web_search: Whether web search was used
        search_context: Pre-fetched search results
        request: FastAPI request for disconnect detection
    """
    settings = get_settings()
    temperature = settings.advisor_temperature

    if not default_model:
        default_model = settings.advisor_default_model
    if not default_model:
        yield {"type": "advisor_error", "message": "No advisor model configured. Set a default model in Settings."}
        return

    personas_list = get_personas_by_ids(persona_ids)
    if len(personas_list) < 2:
        yield {"type": "advisor_error", "message": "At least 2 valid advisors required."}
        return

    personas_map = {p.id: p for p in personas_list}

    search_context_block = ""
    if search_context:
        search_context_block = (
            "You have access to the following real-time web search results. "
            "Use this information if relevant to the debate.\n\n"
            f"Search Results:\n{search_context}\n\n"
        )

    yield {
        "type": "advisor_debate_start",
        "data": {
            "personas": [p.model_dump() for p in personas_list],
            "max_rounds": max_rounds,
            "question": question,
            "web_search": web_search,
        },
    }

    all_rounds: List[Dict[str, Any]] = []
    consensus_reached = False

    for round_num in range(1, max_rounds + 1):
        if request and await request.is_disconnected():
            logger.info("Client disconnected during advisor debate.")
            return

        is_first_round = round_num == 1
        order = build_rotation_order(persona_ids, round_num)

        yield {
            "type": "advisor_round_start",
            "data": {"round_number": round_num, "order": order, "is_parallel": True},
        }

        round_responses: List[Dict[str, Any]] = []
        consensus_votes: Dict[str, bool] = {}

        if is_first_round:
            prompt_template = ADVISOR_ROUND1_PROMPT.format(
                search_context_block=search_context_block,
                question=question,
                consensus_tag=CONSENSUS_TAG_INSTRUCTION,
            )
        else:
            transcript_text = _format_transcript(all_rounds, personas_map)
            prompt_template = ADVISOR_FOLLOWUP_PROMPT.format(
                search_context_block=search_context_block if round_num == 2 else "",
                question=question,
                transcript=transcript_text,
                round_number=round_num,
                consensus_tag=CONSENSUS_TAG_INSTRUCTION,
            )

        async def _query_advisor(pid: str, prompt: str):
            persona = personas_map[pid]
            model = _resolve_model(pid, model_assignments, default_model)
            messages = [
                {"role": "system", "content": persona.system_prompt},
                {"role": "user", "content": prompt},
            ]
            try:
                result = await query_model(model, messages, temperature=temperature)
                if result.get("error"):
                    return pid, model, None, result.get("error_message", "Model error")
                return pid, model, result.get("content", ""), None
            except Exception as e:
                return pid, model, None, str(e)

        tasks = [asyncio.create_task(_query_advisor(pid, prompt_template)) for pid in order]

        pending = set(tasks)
        completed_count = 0
        try:
            while pending:
                if request and await request.is_disconnected():
                    for t in pending:
                        t.cancel()
                    return

                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0
                )

                for task in done:
                    pid, model, content, error = await task
                    completed_count += 1

                    if error:
                        resp_data = {
                            "persona_id": pid,
                            "persona_name": personas_map[pid].name,
                            "model": model,
                            "content": None,
                            "error": error,
                            "consensus": False,
                        }
                    else:
                        has_consensus = parse_consensus_tag(content)
                        clean_content = strip_consensus_tag(content)
                        consensus_votes[pid] = has_consensus
                        resp_data = {
                            "persona_id": pid,
                            "persona_name": personas_map[pid].name,
                            "model": model,
                            "content": clean_content,
                            "error": None,
                            "consensus": has_consensus,
                        }

                    round_responses.append(resp_data)

                    yield {
                        "type": "advisor_response",
                        "data": resp_data,
                        "round": round_num,
                        "count": completed_count,
                        "total": len(order),
                    }

        except asyncio.CancelledError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            return

        successful_responses = [r for r in round_responses if r["error"] is None]
        all_rounds.append({
            "round_number": round_num,
            "responses": [
                {"persona_id": r["persona_id"], "persona_name": r["persona_name"],
                 "model": r["model"], "content": r["content"]}
                for r in successful_responses
            ],
        })

        all_agree = (
            len(consensus_votes) >= 2
            and all(consensus_votes.values())
            and len(consensus_votes) == len(successful_responses)
        )

        yield {
            "type": "advisor_round_complete",
            "data": {
                "round_number": round_num,
                "responses": round_responses,
                "consensus_votes": {k: v for k, v in consensus_votes.items()},
                "consensus_reached": all_agree,
            },
        }

        if all_agree:
            consensus_reached = True
            break

    transcript_text = _format_transcript(all_rounds, personas_map)

    tiebreaker_result = None
    if not consensus_reached and len(persona_ids) == 2:
        tiebreaker_model = settings.advisor_tiebreaker_model or default_model
        yield {"type": "advisor_tiebreaker_start"}

        tiebreaker_prompt = ADVISOR_TIEBREAKER_PROMPT.format(
            question=question,
            transcript=transcript_text,
        )
        try:
            tb_response = await query_model(
                tiebreaker_model,
                [{"role": "user", "content": tiebreaker_prompt}],
                temperature=0.3,
            )
            if tb_response.get("error"):
                tiebreaker_result = {"model": tiebreaker_model, "content": None,
                                     "error": tb_response.get("error_message")}
            else:
                tiebreaker_result = {"model": tiebreaker_model,
                                     "content": tb_response.get("content", ""),
                                     "error": None}
        except Exception as e:
            tiebreaker_result = {"model": tiebreaker_model, "content": None, "error": str(e)}

        yield {"type": "advisor_tiebreaker", "data": tiebreaker_result}

    yield {"type": "advisor_verdict_start"}

    verdict_prompt = ADVISOR_VERDICT_PROMPT.format(
        question=question,
        transcript=transcript_text,
    )

    if tiebreaker_result and tiebreaker_result.get("content"):
        verdict_prompt += f"\n\nTiebreaker ruling:\n{tiebreaker_result['content']}"

    verdict_model = settings.advisor_tiebreaker_model or default_model
    try:
        v_response = await query_model(
            verdict_model,
            [{"role": "user", "content": verdict_prompt}],
            temperature=0.3,
        )
        if v_response.get("error"):
            verdict_data = {"content": None, "model": verdict_model,
                           "error": v_response.get("error_message")}
        else:
            verdict_data = {"content": v_response.get("content", ""),
                           "model": verdict_model, "error": None}
    except Exception as e:
        verdict_data = {"content": None, "model": verdict_model, "error": str(e)}

    yield {"type": "advisor_verdict", "data": verdict_data}

    yield {
        "type": "advisor_complete",
        "data": {
            "rounds": all_rounds,
            "consensus_reached": consensus_reached,
            "tiebreaker": tiebreaker_result,
            "verdict": verdict_data,
        },
    }
