# SaaS Boilerplate — CLAUDE.md

## What this repo is
A personal reusable SaaS boilerplate. The goal is to implement auth, billing, user
dashboard, admin panel, transactional emails, rate limiting, and legal pages **once**,
so future projects only add product-specific code.

## Stack
- **Backend**: FastAPI + SQLAlchemy async (Supabase/PostgreSQL via asyncpg)
- **Frontend**: Vanilla JS (ES modules, no bundler)
- **Billing**: Stripe (Checkout or Elements, config flag)
- **Email**: Resend SDK
- **Deploy**: Railway (backend) + Vercel (frontend)

## Per-project checklist (new project setup)
1. Copy `.env.example` → `.env`, fill in all values
2. Edit `backend/config.py` — all `# EDIT PER PROJECT` lines
3. Edit `backend/plans.py` — real Stripe price IDs + product-specific limits
4. Mirror changes in `frontend/config.js` and `frontend/plans.js`
5. Replace `{{PLACEHOLDERS}}` in `frontend/pages/legal/*.html`
6. Run `bash scripts/setup-env.sh` (or `scripts/new-project.sh` for fresh clone)
7. Create Stripe products + prices, set webhook endpoint to `/api/billing/webhook`
8. Verify Resend sending domain
9. Run all tests — they must be green before deploying

## Critical rule: never hardcode plan data
`backend/plans.py` and `frontend/plans.js` are the **single source of truth**.
Never write plan names, prices, or limits anywhere else.

## Never touch per project
- `backend/core/` — auth, billing, email logic
- `backend/middleware/` — auth_guard, rate_limit
- `frontend/lib/` — api, auth, subscription, admin

Only configure via `config.py`, `plans.py`, and their frontend mirrors.

## Mandatory workflow after any code change
1. Run tests:
   ```bash
   cd backend
   python -m pytest tests/unit tests/integration -v
   ```
2. If **all tests pass** → commit immediately:
   ```bash
   git add -A && git commit -m "feat|fix|refactor: <description>"
   ```
3. If **any test fails** → fix first, only commit after everything is green.

**Never commit broken code.**

## Dev server
```bash
# Backend
uvicorn backend.main:app --reload

# Frontend (from repo root)
npx serve frontend/
```

## Billing modes
- `BILLING_MODE=checkout` — redirects to Stripe Checkout (simpler)
- `BILLING_MODE=elements` — inline Stripe Elements (more custom UI)
Set in `.env` and mirrored in `frontend/config.js`.

## Paywall modes
- `PAYWALL_MODE=modal` — shows in-page upgrade modal
- `PAYWALL_MODE=redirect` — redirects to `/dashboard/plan`
Set in `.env` and mirrored in `frontend/config.js`.
