"""
models/user.py — All SQLAlchemy ORM models for users and auth.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(512), nullable=True)

    # Auth
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_provider: Mapped[str] = mapped_column(String(50), default="magic_link")  # "magic_link" | "google"

    # Billing
    plan: Mapped[str] = mapped_column(String(50), default="free")
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(50), nullable=True)  # active | trialing | canceled | past_due
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    magic_link_tokens: Mapped[list["MagicLinkToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cancellations: Mapped[list["UserCancellation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    rate_limit_logs: Mapped[list["RateLimitLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="magic_link_tokens")


class UserCancellation(Base):
    __tablename__ = "user_cancellations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="cancellations")


class RateLimitLog(Base):
    __tablename__ = "rate_limit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship(back_populates="rate_limit_logs")
