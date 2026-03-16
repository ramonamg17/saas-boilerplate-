"""
plans.py — Single source of truth for plan definitions.

EDIT PER PROJECT:
  - Set real Stripe price IDs
  - Adjust limits to match your product
  - Add/remove plans as needed

Shape:
    {
        key: str,           # internal identifier, matches Stripe metadata
        name: str,          # display name
        price: float,       # USD per month (0 = free)
        stripe_price_id: str,
        trial_days: int,
        limits: {
            requests_per_hour: int,   # used by rate_limit middleware
            # add product-specific limits here  EDIT PER PROJECT
        }
    }
"""

from typing import TypedDict


class PlanLimits(TypedDict):
    requests_per_hour: int


class Plan(TypedDict):
    key: str
    name: str
    price: float
    stripe_price_id: str
    trial_days: int
    limits: PlanLimits


# ─────────────────────────────────────────────────────────────
#  EDIT PER PROJECT — replace placeholder Stripe price IDs
# ─────────────────────────────────────────────────────────────

PLANS: dict[str, Plan] = {
    "free": {
        "key": "free",
        "name": "Free",
        "price": 0.0,
        "stripe_price_id": "",          # EDIT PER PROJECT
        "trial_days": 0,
        "limits": {
            "requests_per_hour": 20,
        },
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price": 19.0,
        "stripe_price_id": "price_placeholder_pro",   # EDIT PER PROJECT
        "trial_days": 14,
        "limits": {
            "requests_per_hour": 500,
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
    return list(PLANS.values())
