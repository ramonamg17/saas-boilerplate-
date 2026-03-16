"""
core/email.py — Transactional email via Resend SDK.

DO NOT EDIT PER PROJECT — add new templates and helpers here.
Configure via config.py (RESEND_API_KEY, EMAIL_FROM, etc.).
"""

import os
from pathlib import Path

import resend

from backend.config import settings
from backend.models.user import User

resend.api_key = settings.RESEND_API_KEY

TEMPLATE_DIR = Path(__file__).parent.parent / "emails"


def _load_template(name: str, replacements: dict) -> str:
    """Load an HTML template and replace {{PLACEHOLDER}} tokens."""
    path = TEMPLATE_DIR / name
    html = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


async def send_email(to: str, subject: str, html: str) -> None:
    """Send a transactional email via Resend."""
    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    })


async def send_magic_link(email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/auth/verify#token={token}"
    html = _load_template("magic_link.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "MAGIC_LINK": link,
    })
    await send_email(email, f"Sign in to {settings.APP_NAME}", html)


async def send_welcome(user: User) -> None:
    html = _load_template("welcome.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "USER_NAME": user.name or user.email,
    })
    await send_email(user.email, f"Welcome to {settings.APP_NAME}!", html)


async def send_subscription_confirmed(user: User, plan_name: str) -> None:
    html = _load_template("subscription_confirmed.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "USER_NAME": user.name or user.email,
        "PLAN_NAME": plan_name,
    })
    await send_email(user.email, f"Your {settings.APP_NAME} subscription is active", html)


async def send_payment_failed(user: User) -> None:
    html = _load_template("payment_failed.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "USER_NAME": user.name or user.email,
    })
    await send_email(user.email, f"Action required: payment failed for {settings.APP_NAME}", html)


async def send_cancellation_confirmed(user: User, period_end: str) -> None:
    html = _load_template("cancellation_confirmed.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "USER_NAME": user.name or user.email,
        "PERIOD_END": period_end,
    })
    await send_email(user.email, f"Your {settings.APP_NAME} subscription has been cancelled", html)


async def send_support_received(user: User, message: str) -> None:
    # Confirmation to user
    html = _load_template("support_received.html", {
        "APP_NAME": settings.APP_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "USER_NAME": user.name or user.email,
        "USER_MESSAGE": message,
    })
    await send_email(user.email, f"We received your message — {settings.APP_NAME}", html)

    # Notification to owner
    owner_html = f"""
    <p><strong>New support request from:</strong> {user.email}</p>
    <p><strong>Message:</strong></p>
    <blockquote>{message}</blockquote>
    """
    await send_email(
        settings.OWNER_EMAIL,
        f"[{settings.APP_NAME}] Support request from {user.email}",
        owner_html,
    )
