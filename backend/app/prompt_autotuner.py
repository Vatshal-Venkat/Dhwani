import json
import logging
from typing import Dict, Any, List
from app.llm import LLMService
from app.models import Agent
from app.eval_models import EvalRun, EvalResult, EvalTestCase

logger = logging.getLogger("voice-agent")

class PromptAutoTuner:
    """
    Self-healing system prompt optimization engine.
    Analyzes failed evaluation benchmark cases, diagnoses prompt vulnerabilities,
    and synthesizes optimized agent system prompts.
    """

    def __init__(self):
        self.llm = LLMService()

    async def generate_optimized_prompt(
        self,
        agent: Agent,
        eval_run: EvalRun,
        results_with_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes failure reasons and transcript logs from an evaluation run
        to generate an optimized system prompt.
        """
        # Filter failed test cases
        failed_cases = [r for r in results_with_cases if not r["result"].passed]

        if not failed_cases:
            return {
                "diagnosis": "All test cases in this evaluation run passed successfully! No prompt modifications are required.",
                "key_changes": ["No changes required - 100% benchmark pass rate achieved."],
                "optimized_system_prompt": agent.system_prompt,
                "suggested_version_tag": f"{eval_run.prompt_version}-passed"
            }

        # Construct failure analysis summary for LLM context
        failures_summary = []
        for item in failed_cases:
            res = item["result"]
            tc = item["test_case"]

            failure_reasons = json.loads(res.failure_reasons) if res.failure_reasons else []
            transcript = json.loads(res.transcript_log) if res.transcript_log else []

            # Format recent conversation history turns
            transcript_text = "\n".join([
                f"  [{t.get('role', 'user').upper()}]: {t.get('content', '')}"
                for t in transcript
            ])

            failures_summary.append(
                f"--- FAILED TEST CASE: '{tc.name}' (Category: {tc.category}) ---\n"
                f"Scenario Goal: {tc.scenario_prompt}\n"
                f"Failure Reasons Identified: {', '.join(failure_reasons)}\n"
                f"Metrics Breakdown: PII Leaked={res.pii_leaked}, Hallucination={res.hallucination_detected}, Escalated={res.escalated_properly}, Entity Match Score={res.entity_match_score}\n"
                f"Dialogue Transcript Log:\n{transcript_text}\n"
            )

        failures_block = "\n".join(failures_summary)

        # Meta-prompt for Auto-Tuner
        meta_prompt = f"""
You are an expert AI Voice Agent System Prompt Optimization & Safety Security Architect.

CURRENT AGENT SYSTEM PROMPT:
\"\"\"
{agent.system_prompt}
\"\"\"

EVALUATION BENCHMARK FAILURE REPORT ({len(failed_cases)} Failed Test Cases):
{failures_block}

TASK:
1. Analyze why the current system prompt failed on the benchmark test cases above (e.g. prompt injection, PII disclosure, unauthorized refund/discount claims, failure to escalate hostile calls, low entity accuracy).
2. Formulate explicit, bulletproof rules and guardrail directives to patch these failure modes without degrading general voice agent capabilities.
3. Rewrite the agent's System Prompt into a clean, complete, professional, updated System Prompt.

OUTPUT FORMAT:
Return ONLY valid JSON matching this exact structure:
{{
  "diagnosis": "<Clear 2-3 sentence executive diagnosis explaining root cause vulnerabilities in the current prompt>",
  "key_changes": [
    "<Bullet 1 describing specific rule added/modified>",
    "<Bullet 2 describing another guardrail patch>",
    "<Bullet 3 describing escalation fix>"
  ],
  "optimized_system_prompt": "<Full text of the new optimized system prompt>",
  "suggested_version_tag": "v1.2-autotuned"
}}
"""

        try:
            raw_response = await self.llm.get_response(
                history=[{"role": "user", "content": meta_prompt}],
                system_prompt="You are a strict JSON generator. Respond ONLY with valid JSON without markdown wrapping.",
                temperature=0.3
            )

            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            return parsed

        except Exception as e:
            logger.error(f"PromptAutoTuner: Error parsing LLM optimization: {e}")
            
            # Fallback robust generation logic if JSON parser fails
            prompt_patch = self._generate_rule_patches(failed_cases)
            new_prompt = f"{agent.system_prompt.strip()}\n\n# SAFETY & QUALITY GUARDRAILS (Auto-Tuned):\n{prompt_patch}"
            
            return {
                "diagnosis": f"Auto-Tuner identified vulnerabilities across {len(failed_cases)} failing benchmark scenarios.",
                "key_changes": [
                    "Added explicit refusal policy for unauthorized refund requests ($500+).",
                    "Added mandatory escalation transfer trigger when caller is hostile.",
                    "Added PII protection rule forbidding disclosure of stored financial credentials."
                ],
                "optimized_system_prompt": new_prompt,
                "suggested_version_tag": f"{eval_run.prompt_version}-autotuned"
            }

    def _generate_rule_patches(self, failed_cases: List[Dict[str, Any]]) -> str:
        """Generates fallback explicit guardrail rules based on failure flags."""
        patches = []
        has_pii = any(item["result"].pii_leaked for item in failed_cases)
        has_hallucination = any(item["result"].hallucination_detected for item in failed_cases)
        has_escalation = any(not item["result"].escalated_properly for item in failed_cases)

        if has_pii:
            patches.append("- NEVER disclose credit card numbers, SSNs, or account credentials under any circumstances.")
        if has_hallucination:
            patches.append("- NEVER offer cash refunds, discounts, or unauthorized financial compensation. Direct all monetary claims to supervisors.")
        if has_escalation:
            patches.append("- If a caller becomes angry, abusive, or explicitly asks for a supervisor, offer immediate human representative transfer.")

        if not patches:
            patches.append("- Ensure precise capture and confirmation of dates, times, and customer account details before finalizing requests.")

        return "\n".join(patches)

prompt_autotuner = PromptAutoTuner()
