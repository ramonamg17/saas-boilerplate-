#!/usr/bin/env bash
# setup-env.sh — Interactive .env generator
# Run from the project root: bash scripts/setup-env.sh

set -euo pipefail

ENV_FILE=".env"

prompt() {
  local var="$1"
  local prompt_text="$2"
  local default="${3:-}"

  if [[ -n "$default" ]]; then
    read -rp "$prompt_text [$default]: " value
    echo "${value:-$default}"
  else
    read -rp "$prompt_text: " value
    echo "$value"
  fi
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SaaS Boilerplate — Environment Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

APP_NAME=$(prompt APP_NAME "App name" "My SaaS App")
FRONTEND_URL=$(prompt FRONTEND_URL "Frontend URL" "http://localhost:3000")
SUPPORT_EMAIL=$(prompt SUPPORT_EMAIL "Support email")
OWNER_EMAIL=$(prompt OWNER_EMAIL "Owner/admin email")

echo ""
echo "── Database ──"
DATABASE_URL=$(prompt DATABASE_URL "DATABASE_URL (postgresql+asyncpg://...)")

echo ""
echo "── Auth ──"
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
echo "JWT_SECRET auto-generated: ${JWT_SECRET:0:8}…"

GOOGLE_CLIENT_ID=$(prompt GOOGLE_CLIENT_ID "Google Client ID (leave blank to skip)" "")
GOOGLE_CLIENT_SECRET=$(prompt GOOGLE_CLIENT_SECRET "Google Client Secret (leave blank to skip)" "")

echo ""
echo "── Stripe ──"
STRIPE_SECRET_KEY=$(prompt STRIPE_SECRET_KEY "Stripe Secret Key (sk_...)")
STRIPE_PUBLISHABLE_KEY=$(prompt STRIPE_PUBLISHABLE_KEY "Stripe Publishable Key (pk_...)")
STRIPE_WEBHOOK_SECRET=$(prompt STRIPE_WEBHOOK_SECRET "Stripe Webhook Secret (whsec_...)" "whsec_placeholder")
BILLING_MODE=$(prompt BILLING_MODE "Billing mode" "checkout")

echo ""
echo "── Email (Resend) ──"
RESEND_API_KEY=$(prompt RESEND_API_KEY "Resend API Key (re_...)")
EMAIL_FROM=$(prompt EMAIL_FROM "From email address" "noreply@${APP_NAME// /-}.com")

echo ""
echo "── Feature flags ──"
PAYWALL_MODE=$(prompt PAYWALL_MODE "Paywall mode (modal/redirect)" "modal")
ENABLE_GUEST_SESSIONS=$(prompt ENABLE_GUEST_SESSIONS "Enable guest sessions (true/false)" "true")
GUEST_NUDGE_AFTER=$(prompt GUEST_NUDGE_AFTER "Guest nudge after N actions" "3")

cat > "$ENV_FILE" <<EOF
APP_NAME="${APP_NAME}"
FRONTEND_URL="${FRONTEND_URL}"
SUPPORT_EMAIL="${SUPPORT_EMAIL}"
OWNER_EMAIL="${OWNER_EMAIL}"

DATABASE_URL="${DATABASE_URL}"

JWT_SECRET="${JWT_SECRET}"
JWT_ALGORITHM="HS256"
JWT_EXPIRE_MINUTES=10080
MAGIC_LINK_EXPIRE_MINUTES=15

GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET}"
GOOGLE_REDIRECT_URI="${FRONTEND_URL}/auth/google/callback"

STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY}"
STRIPE_PUBLISHABLE_KEY="${STRIPE_PUBLISHABLE_KEY}"
STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET}"
BILLING_MODE="${BILLING_MODE}"

RESEND_API_KEY="${RESEND_API_KEY}"
EMAIL_FROM="${EMAIL_FROM}"

PAYWALL_MODE="${PAYWALL_MODE}"
ENABLE_GUEST_SESSIONS="${ENABLE_GUEST_SESSIONS}"
GUEST_NUDGE_AFTER=${GUEST_NUDGE_AFTER}

RATE_LIMIT_WINDOW_SECONDS=3600
EOF

echo ""
echo "✓ .env written."
echo ""
echo "Next steps:"
echo "  1. pip install -r requirements.txt"
echo "  2. Edit backend/plans.py — set real Stripe price IDs"
echo "  3. Edit frontend/config.js — set API_BASE_URL for production"
echo "  4. uvicorn backend.main:app --reload"
echo ""
