"""
plans.py — Subscription plan definitions for TTS English Phrases.

Limits:
  guest:  1 session/day,  max 5 min duration
  free:   5 sessions/month, max 15 min duration
  pro:    unlimited sessions, all durations (up to 30 min)
"""

from typing import TypedDict


class PlanLimits(TypedDict):
    requests_per_hour: int
    sessions_per_day: int    # used for guest plan; 0 = not applicable
    sessions_per_month: int  # used for free plan; 0 = unlimited
    max_duration_minutes: int


class Plan(TypedDict):
    key: str
    name: str
    price: float
    stripe_price_id: str
    trial_days: int
    limits: PlanLimits


PLANS: dict[str, Plan] = {
    "guest": {
        "key": "guest",
        "name": "Guest",
        "price": 0.0,
        "stripe_price_id": "",
        "trial_days": 0,
        "limits": {
            "requests_per_hour": 10,
            "sessions_per_day": 1,
            "sessions_per_month": 0,
            "max_duration_minutes": 5,
        },
    },
    "free": {
        "key": "free",
        "name": "Free",
        "price": 0.0,
        "stripe_price_id": "",
        "trial_days": 0,
        "limits": {
            "requests_per_hour": 20,
            "sessions_per_day": 0,
            "sessions_per_month": 5,
            "max_duration_minutes": 15,
        },
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price": 19.0,
        "stripe_price_id": "price_placeholder_pro",  # EDIT: replace with real Stripe price ID
        "trial_days": 14,
        "limits": {
            "requests_per_hour": 500,
            "sessions_per_day": 0,
            "sessions_per_month": 0,  # 0 = unlimited
            "max_duration_minutes": 30,
        },
    },
}


def get_plan(key: str) -> Plan:
    """Return a plan by key, falling back to 'free' if not found."""
    return PLANS.get(key, PLANS["free"])


def get_plan_limit(plan_key: str, limit_name: str) -> int:
    """Return a specific limit for a plan."""
    plan = get_plan(plan_key)
    return plan["limits"].get(limit_name, 0)


def all_plans() -> list[Plan]:
    """Return all plans (excluding internal guest plan for public display)."""
    return [PLANS["free"], PLANS["pro"]]
