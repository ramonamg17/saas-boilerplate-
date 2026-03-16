# Backend — CLAUDE.md

## Structure
```
backend/
├── config.py          # All settings (single source of truth)
├── plans.py           # Plan definitions (single source of truth)
├── database.py        # Async SQLAlchemy engine + get_db dependency
├── main.py            # FastAPI app, CORS, router inclusion, lifespan
├── models/
│   └── user.py        # User, MagicLinkToken, UserCancellation, RateLimitLog
├── core/
│   ├── auth.py        # JWT, magic link, Google OAuth
│   ├── billing.py     # All Stripe interactions
│   └── email.py       # Resend transactional emails
├── middleware/
│   ├── auth_guard.py  # get_current_user, require_admin, optional_user
│   └── rate_limit.py  # Sliding window rate limiter
├── routers/
│   ├── auth.py        # /api/auth/*
│   ├── billing.py     # /api/billing/*
│   ├── user.py        # /api/user/*
│   └── admin.py       # /api/admin/*
├── emails/            # HTML email templates with {{PLACEHOLDERS}}
└── tests/
    ├── conftest.py    # Shared fixtures, SQLite in-memory
    ├── unit/          # Fast, no DB required
    └── integration/   # ASGI test client + real SQLite
```

## Rules
- **Never edit** `core/`, `middleware/` per project — configure via `config.py` only
- `plans.py` is the single source of truth — all rate limits read from here
- All Stripe interactions go through `core/billing.py`
- All email sends go through `core/email.py`
- Route protection: always use `Depends(get_current_user)` or `Depends(require_admin)`
- Rate limiting: use `rate_limit("action_name")` as a route dependency

## Adding a new route
1. Add the endpoint function to the appropriate router in `routers/`
2. Protect it with `Depends(get_current_user)` if auth is required
3. Add rate limiting with `rate_limit("action_key")` if needed
4. Add integration tests in `tests/integration/`

## Adding a new email
1. Create `emails/<name>.html` with `{{PLACEHOLDER}}` tokens
2. Add a `send_<name>()` function in `core/email.py`
3. Call it from the appropriate router or webhook handler

## Environment variables
All are in `config.py` with defaults. Never use `os.environ` directly — use `settings.*`.

## Test commands
```bash
python -m pytest tests/unit -v          # unit only (fast)
python -m pytest tests/integration -v  # integration only
python -m pytest tests/ -v             # all
```
