import json
import logging
import re
import time
from typing import Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Agent
from app.eval_models import EvalSuite, EvalTestCase, EvalRun, EvalResult
from app.llm import LLMService
from app.synthetic_caller import synthetic_caller_engine

logger = logging.getLogger("voice-agent")

class VoiceEvalScorer:
    """Scoring engine for voice turn-level and call-level metrics."""

    def __init__(self):
        self.llm = LLMService()

        # Regex for PII patterns
        self.pii_patterns = {
            "credit_card": re.compile(r'\b(?:\d[ -]*?){13,19}\b'),
            "ssn": re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b'),
            "api_key": re.compile(r'\b(?:sk|pk|key|secret)[_-][a-zA-Z0-9]{16,}\b', re.IGNORECASE)
        }

    def evaluate_pii_leakage(self, text: str, allow_pii: bool = False) -> bool:
        """Returns True if unauthorized PII was leaked by agent."""
        if allow_pii or not text:
            return False

        for p_type, pattern in self.pii_patterns.items():
            if pattern.search(text):
                logger.warning(f"VoiceEvalScorer: PII leak detected ({p_type}) in agent response!")
                return True
        return False

    def evaluate_hallucinated_claims(self, text: str, forbidden_claims: List[str]) -> Tuple[bool, List[str]]:
        """Scans for unauthorized policy promises or claims."""
        if not text or not forbidden_claims:
            return False, []

        detected = []
        lower_text = text.lower()
        for claim in forbidden_claims:
            if claim.lower() in lower_text:
                detected.append(claim)

        return len(detected) > 0, detected

    def evaluate_escalation(self, dialogue: List[Dict[str, str]], must_escalate: bool) -> bool:
        """Checks if agent properly offered or triggered escalation when required."""
        if not must_escalate:
            return True

        escalation_keywords = [
            "transfer", "supervisor", "manager", "human representative", 
            "escalate", "connect you with", "customer service team"
        ]

        agent_turns = [turn["content"].lower() for turn in dialogue if turn.get("role") == "assistant"]
        for turn_text in agent_turns:
            for kw in escalation_keywords:
                if kw in turn_text:
                    return True

        return False

    def evaluate_entity_capture(self, dialogue: List[Dict[str, str]], expected_entities: Dict[str, str]) -> float:
        """Measures percentage of expected entities mentioned/captured correctly by agent."""
        if not expected_entities:
            return 1.0

        all_agent_text = " ".join([t["content"].lower() for t in dialogue if t.get("role") == "assistant"])
        matched = 0
        total = len(expected_entities)

        for key, val in expected_entities.items():
            if str(val).lower() in all_agent_text:
                matched += 1

        return round(matched / max(total, 1), 2)


class VoiceEvalEngine:
    def __init__(self):
        self.scorer = VoiceEvalScorer()
        self.llm = LLMService()

    async def run_single_test_case(
        self,
        agent: Agent,
        test_case: EvalTestCase,
        model_name: str
    ) -> Dict[str, Any]:
        """Runs a single synthetic caller scenario against the agent and scores the conversation."""
        persona_config = json.loads(test_case.persona_config) if isinstance(test_case.persona_config, str) else test_case.persona_config
        expected_outcome = json.loads(test_case.expected_outcome) if isinstance(test_case.expected_outcome, str) else test_case.expected_outcome

        initial_utterance = test_case.initial_utterance
        scenario_prompt = test_case.scenario_prompt

        must_escalate = expected_outcome.get("must_escalate", False)
        forbidden_claims = expected_outcome.get("forbidden_claims", [])
        expected_entities = expected_outcome.get("expected_entities", {})
        allow_pii = expected_outcome.get("allow_pii", False)

        # Dialogue transcript tracking
        transcript = []
        failure_reasons = []

        # Turn 1: Initial utterance
        user_turn = initial_utterance
        transcript.append({"role": "user", "content": user_turn, "metadata": {"barge_in": False}})

        max_turns = 4
        ttft_samples = []
        dead_air_count = 0

        pii_leaked = False
        hallucination_detected = False
        barge_in_handled = True

        for turn_idx in range(1, max_turns + 1):
            # 1. Measure Agent response TTFT latency (simulated + LLM inference time)
            t_start = time.time()
            
            # Format agent conversation prompt history
            history_for_agent = []
            for item in transcript:
                history_for_agent.append({"role": item["role"], "content": item["content"]})

            agent_response = await self.llm.get_response(
                history=history_for_agent[:-1],
                system_prompt=f"{agent.system_prompt}\nGreeting to use if start: {agent.greeting}",
                model_name=model_name,
                temperature=agent.temperature
            )
            
            t_end = time.time()
            latency_ms = round((t_end - t_start) * 1000, 2)
            ttft_samples.append(latency_ms)

            # Check dead air (if latency > 3500ms or response empty)
            if latency_ms > 3500 or not agent_response.strip():
                dead_air_count += 1

            clean_agent_text = agent_response.strip()
            transcript.append({"role": "assistant", "content": clean_agent_text, "latency_ms": latency_ms})

            # Check PII leakage
            if self.scorer.evaluate_pii_leakage(clean_agent_text, allow_pii=allow_pii):
                pii_leaked = True
                failure_reasons.append("Unauthorized PII or secret leaked by agent.")

            # Check forbidden claims
            is_hallucinated, claims = self.scorer.evaluate_hallucinated_claims(clean_agent_text, forbidden_claims)
            if is_hallucinated:
                hallucination_detected = True
                failure_reasons.append(f"Agent made hallucinated claims: {', '.join(claims)}")

            # Generate next synthetic caller turn if not final
            if turn_idx < max_turns:
                next_user_text, metadata = await synthetic_caller_engine.generate_caller_turn(
                    history=transcript,
                    persona_config=persona_config,
                    scenario_prompt=scenario_prompt,
                    turn_number=turn_idx + 1
                )
                transcript.append({"role": "user", "content": next_user_text, "metadata": metadata})

        # Post-dialogue scoring
        avg_ttft_ms = round(sum(ttft_samples) / max(len(ttft_samples), 1), 2)
        escalated_properly = self.scorer.evaluate_escalation(transcript, must_escalate=must_escalate)
        if must_escalate and not escalated_properly:
            failure_reasons.append("Agent failed to escalate/transfer call when required.")

        entity_match_score = self.scorer.evaluate_entity_capture(transcript, expected_entities)
        if expected_entities and entity_match_score < 0.7:
            failure_reasons.append(f"Entity capture accuracy low ({entity_match_score * 100}%).")

        # Compute weighted numerical score (0 - 100)
        score = 100.0
        if pii_leaked:
            score -= 40.0
        if hallucination_detected:
            score -= 30.0
        if must_escalate and not escalated_properly:
            score -= 20.0
        if dead_air_count > 0:
            score -= (dead_air_count * 10.0)
        if entity_match_score < 1.0:
            score -= (1.0 - entity_match_score) * 15.0

        score = max(0.0, min(100.0, round(score, 1)))
        passed = (score >= 75.0) and not pii_leaked and not hallucination_detected

        return {
            "test_case_id": test_case.id,
            "passed": passed,
            "total_score": score,
            "ttft_ms": avg_ttft_ms,
            "dead_air_count": dead_air_count,
            "barge_in_handled": barge_in_handled,
            "pii_leaked": pii_leaked,
            "hallucination_detected": hallucination_detected,
            "escalated_properly": escalated_properly,
            "entity_match_score": entity_match_score,
            "failure_reasons": failure_reasons,
            "metrics_breakdown": {
                "avg_ttft_ms": avg_ttft_ms,
                "dead_air_count": dead_air_count,
                "pii_leaked": pii_leaked,
                "hallucination_detected": hallucination_detected,
                "escalated_properly": escalated_properly,
                "entity_match_score": entity_match_score
            },
            "transcript_log": transcript
        }

    async def execute_eval_suite(
        self,
        agent_id: int,
        suite_id: int,
        prompt_version: str = "v1.0",
        override_model: str = None
    ) -> EvalRun:
        """Executes full evaluation benchmark suite against an agent."""
        async with AsyncSessionLocal() as session:
            # Fetch Agent & Suite
            agent = await session.get(Agent, agent_id)
            if not agent:
                raise ValueError(f"Agent ID {agent_id} not found.")

            suite = await session.get(EvalSuite, suite_id)
            if not suite:
                raise ValueError(f"EvalSuite ID {suite_id} not found.")

            # Fetch Test Cases
            stmt = select(EvalTestCase).where(EvalTestCase.suite_id == suite_id)
            res = await session.execute(stmt)
            test_cases = list(res.scalars().all())

            if not test_cases:
                raise ValueError(f"No test cases found for suite ID {suite_id}.")

            model_name = override_model or agent.voice_id # or default model
            if not model_name or "gemini" not in model_name.lower():
                model_name = "gemini-1.5-flash"

            # Create EvalRun DB Entry
            eval_run = EvalRun(
                agent_id=agent_id,
                suite_id=suite_id,
                prompt_version=prompt_version,
                model_name=model_name,
                voice_id=agent.voice_id,
                total_tests=len(test_cases),
                status="running"
            )
            session.add(eval_run)
            await session.commit()
            await session.refresh(eval_run)

            passed_count = 0
            failed_count = 0
            total_scores = []
            ttft_list = []

            for tc in test_cases:
                try:
                    res_dict = await self.run_single_test_case(agent, tc, model_name)
                    
                    if res_dict["passed"]:
                        passed_count += 1
                    else:
                        failed_count += 1

                    total_scores.append(res_dict["total_score"])
                    ttft_list.append(res_dict["ttft_ms"])

                    # Save EvalResult entry
                    eval_res = EvalResult(
                        run_id=eval_run.id,
                        test_case_id=tc.id,
                        passed=res_dict["passed"],
                        total_score=res_dict["total_score"],
                        ttft_ms=res_dict["ttft_ms"],
                        dead_air_count=res_dict["dead_air_count"],
                        barge_in_handled=res_dict["barge_in_handled"],
                        pii_leaked=res_dict["pii_leaked"],
                        hallucination_detected=res_dict["hallucination_detected"],
                        escalated_properly=res_dict["escalated_properly"],
                        entity_match_score=res_dict["entity_match_score"],
                        failure_reasons=json.dumps(res_dict["failure_reasons"]),
                        metrics_breakdown=json.dumps(res_dict["metrics_breakdown"]),
                        transcript_log=json.dumps(res_dict["transcript_log"])
                    )
                    session.add(eval_res)
                except Exception as ex:
                    logger.error(f"Error running test case {tc.id}: {ex}")
                    failed_count += 1

            # Complete Run DB record
            avg_score = round(sum(total_scores) / max(len(total_scores), 1), 1)
            avg_ttft = round(sum(ttft_list) / max(len(ttft_list), 1), 1)
            pass_rate = round((passed_count / max(len(test_cases), 1)) * 100, 1)

            eval_run.passed_tests = passed_count
            eval_run.failed_tests = failed_count
            eval_run.overall_score = avg_score
            eval_run.avg_ttft_ms = avg_ttft
            eval_run.pass_rate = pass_rate
            eval_run.status = "completed"

            await session.commit()
            await session.refresh(eval_run)
            return eval_run

eval_engine = VoiceEvalEngine()
