from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class EvalSuite(Base):
    __tablename__ = "eval_suites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="Adversarial & Persona")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EvalTestCase(Base):
    __tablename__ = "eval_test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_suites.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="Adversarial") # Security, Persona, Escalation, Quality
    
    # JSON strings for structured configuration
    persona_config: Mapped[str] = mapped_column(Text, nullable=False) # accent, noise, hostility, interrupter, off_script, jailbreak
    scenario_prompt: Mapped[str] = mapped_column(Text, nullable=False) # system prompt instructing synthetic caller
    initial_utterance: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False) # must_escalate, forbidden_claims, expected_entities, allow_pii
    
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), nullable=False)
    suite_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_suites.id"), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), default="v1.0")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_ttft_ms: Mapped[float] = mapped_column(Float, default=0.0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="completed") # running, completed, failed
    
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_test_cases.id"), nullable=False)
    
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Detailed Turn & Voice Metrics
    ttft_ms: Mapped[float] = mapped_column(Float, default=0.0)
    dead_air_count: Mapped[int] = mapped_column(Integer, default=0)
    barge_in_handled: Mapped[bool] = mapped_column(Boolean, default=True)
    pii_leaked: Mapped[bool] = mapped_column(Boolean, default=False)
    hallucination_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_properly: Mapped[bool] = mapped_column(Boolean, default=True)
    entity_match_score: Mapped[float] = mapped_column(Float, default=1.0)
    
    failure_reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON list of reasons
    metrics_breakdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON details
    transcript_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON transcript turns
    
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
