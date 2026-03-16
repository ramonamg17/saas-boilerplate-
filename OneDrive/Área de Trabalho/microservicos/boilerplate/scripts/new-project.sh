#!/usr/bin/env bash
# new-project.sh — Clone the boilerplate and set up a new project
# Usage: bash new-project.sh <project-name> [target-directory]

set -euo pipefail

BOILERPLATE_REPO="https://github.com/YOUR_USERNAME/saas-boilerplate"  # EDIT: set your repo URL
PROJECT_NAME="${1:-my-saas-app}"
TARGET_DIR="${2:-$PROJECT_NAME}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Creating new project: $PROJECT_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Clone
git clone "$BOILERPLATE_REPO" "$TARGET_DIR"
cd "$TARGET_DIR"

# Remove boilerplate git history and start fresh
rm -rf .git
git init
git add -A
git commit -m "chore: init from saas-boilerplate"

echo ""
echo "✓ Repository initialized."
echo ""

# Run environment setup
bash scripts/setup-env.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Per-project checklist"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  [ ] backend/config.py — review all # EDIT PER PROJECT lines"
echo "  [ ] backend/plans.py  — set real Stripe price IDs + limits"
echo "  [ ] frontend/config.js — set API_BASE_URL, STRIPE_PUBLISHABLE_KEY"
echo "  [ ] frontend/plans.js  — mirror backend/plans.py"
echo "  [ ] frontend/pages/legal/*.html — replace {{PLACEHOLDERS}}"
echo "  [ ] Stripe: create products + prices in dashboard"
echo "  [ ] Stripe: configure webhook endpoint → /api/billing/webhook"
echo "  [ ] Resend: verify sending domain"
echo "  [ ] Railway: add environment variables from .env"
echo "  [ ] Vercel: deploy frontend/ directory"
echo "  [ ] Test magic link flow end-to-end"
echo "  [ ] Test Stripe checkout + webhook locally (stripe listen)"
echo ""
echo "  Run tests:"
echo "    pip install -r requirements.txt"
echo "    cd backend && python -m pytest tests/ -v"
echo ""
echo "Done! cd $TARGET_DIR and start building."
echo ""
