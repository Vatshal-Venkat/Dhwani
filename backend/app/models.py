from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    voice_id = Column(String(255), nullable=False)
    temperature = Column(Float, default=0.7)
    system_prompt = Column(Text, nullable=False)
    greeting = Column(Text, nullable=False)
    creator_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    duration = Column(Integer, default=0) # in seconds
    status = Column(String(50), default="completed") # e.g. completed, failed, interrupted
    transcription_log = Column(Text, nullable=True) # JSON representation of transcripts
    cost = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    disposition = Column(String(100), nullable=True)
    structured_outcome = Column(Text, nullable=True) # JSON string representation

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider = Column(String(100), unique=True, nullable=False) # e.g. gemini, groq
    encrypted_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
