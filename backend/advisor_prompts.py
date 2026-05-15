"""Prompt templates for the LLM Advisors debate system."""

CONSENSUS_TAG_INSTRUCTION = (
    "\n\nIMPORTANT: At the very end of your response, on its own line, write exactly "
    "CONSENSUS:YES if you believe the group has reached substantial agreement on the core answer, "
    "or CONSENSUS:NO if there are still meaningful disagreements worth debating. "
    "Do not explain this tag — just write it as the last line."
)

ADVISOR_ROUND1_PROMPT = (
    "{search_context_block}"
    "You are participating in a structured debate as an advisor.\n\n"
    "The question being debated:\n{question}\n\n"
    "State your position clearly and support it with reasoning. Be direct and concise — "
    "aim for 150-300 words. Do not hedge excessively."
    "{consensus_tag}"
)

ADVISOR_FOLLOWUP_PROMPT = (
    "{search_context_block}"
    "You are participating in a structured debate as an advisor.\n\n"
    "The question being debated:\n{question}\n\n"
    "Here is the debate so far:\n\n{transcript}\n\n"
    "This is Round {round_number}. Respond to the other advisors' arguments. "
    "You may strengthen your position, concede points, or shift your view if persuaded. "
    "Reference specific arguments by name. Be direct and concise — aim for 150-300 words."
    "{consensus_tag}"
)

ADVISOR_VERDICT_PROMPT = (
    "You are a neutral analyst reviewing a structured debate between advisors.\n\n"
    "The original question:\n{question}\n\n"
    "Full debate transcript:\n{transcript}\n\n"
    "Produce a structured verdict in the following exact format. Use markdown formatting.\n\n"
    "## Summary\n"
    "2-3 sentences capturing the key insight from this debate.\n\n"
    "## Consensus Points\n"
    "Bulleted list of points where all advisors agreed.\n\n"
    "## Disagreements\n"
    "For each disagreement, create a row with: the point of contention, each side's position, "
    "and which argument had stronger evidence. Use a markdown table with columns: "
    "Point | Position A | Position B | Stronger Argument.\n\n"
    "## Verdict\n"
    "State which overall position was strongest and why, naming the advisor(s) who made "
    "the most compelling case. If the debate reached consensus, say so.\n\n"
    "## Recommended Next Steps\n"
    "3-5 concrete, actionable next steps based on the debate outcome.\n\n"
    "## Open Uncertainties\n"
    "Bulleted list of questions that remain unresolved after the debate."
)

ADVISOR_TIEBREAKER_PROMPT = (
    "You are a neutral tiebreaker called in because the advisors could not reach agreement.\n\n"
    "The original question:\n{question}\n\n"
    "Full debate transcript:\n{transcript}\n\n"
    "The advisors' positions are evenly split. Your job is to:\n"
    "1. Identify the strongest arguments from each side\n"
    "2. Weigh the evidence and reasoning\n"
    "3. Deliver a clear decision — which position should prevail and why\n"
    "4. If appropriate, propose a synthesis that takes the best from both sides\n\n"
    "Be decisive. Do not equivocate."
)
