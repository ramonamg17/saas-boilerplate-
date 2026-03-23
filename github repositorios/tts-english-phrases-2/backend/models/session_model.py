"""
models/session_model.py — TTS session persistence model.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class TtsSession(Base):
    __tablename__ = "tts_sessions"

    # Use String(36) instead of PostgreSQL UUID type for SQLite test compatibility
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guest_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    audio_url: Mapped[str] = mapped_column(Text, nullable=True)
    preview_url: Mapped[str] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    phrases_done: Mapped[int] = mapped_column(Integer, default=0)
    phrases_total: Mapped[int] = mapped_column(Integer, default=0)

    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(100), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
