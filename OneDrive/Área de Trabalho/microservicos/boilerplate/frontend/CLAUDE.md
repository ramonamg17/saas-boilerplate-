# Frontend — CLAUDE.md

## Structure
```
frontend/
├── config.js          # App config (mirror of backend/config.py)
├── plans.js           # Plan definitions (mirror of backend/plans.py)
├── lib/
│   ├── api.js         # Fetch wrapper, auto JWT header, 401 → auth:logout
│   ├── auth.js        # JWT lifecycle, guest sessions, magic link callback
│   ├── subscription.js# Billing status, paywall gating, upgrade flow
│   └── admin.js       # Admin API helpers
├── components/
│   ├── auth-modal.js  # Magic link + Google sign-in logic
│   ├── paywall.js     # Upgrade modal (PAYWALL_MODE=modal)
│   ├── guest-nudge.js # Banner after N guest actions
│   └── toast.js       # Queue-based toast notifications
└── pages/
    ├── dashboard/     # account, plan, cancel, billing, delete, contact
    ├── admin/         # users list, user detail
    └── legal/         # privacy, terms, cookies, refund (with {{PLACEHOLDERS}})
```

## Rules
- **Never edit** `lib/` per project — configure via `config.js` and `plans.js` only
- All API calls go through `lib/api.js` — never call `fetch()` directly
- All auth state goes through `lib/auth.js` — never touch `localStorage` directly
- Listen for `auth:login` / `auth:logout` events; never poll auth state
- Use `subscription.gate("feature")` to protect features behind a paywall

## Key events (window CustomEvent)
| Event | When | Detail |
|---|---|---|
| `auth:login` | User authenticates | `{ user }` |
| `auth:logout` | Token invalid / manual logout | — |
| `auth:show-modal` | Trigger auth modal | — |
| `guest:nudge` | After N guest actions | `{ count }` |
| `subscription:paywall-shown` | Gate blocked | `{ feature }` |
| `subscription:upgraded` | Elements billing | `{ plan, client_secret }` |

## Page pattern
Every page should:
1. Import `auth` and call `await auth.init()` first
2. Redirect to `/` if auth is required and user is not logged in
3. Import `toast` for user feedback
4. Use `api.get/post/patch/delete` for all API calls

## Adding a new page
1. Create `pages/<section>/<name>.html`
2. Use `<script type="module">` with ES module imports
3. Call `auth.init()` at the top of the script
4. Add a link to it from the dashboard navigation

## Legal pages
Replace all `{{PLACEHOLDER}}` tokens before deploying:
- `{{APP_NAME}}` — your app name
- `{{SUPPORT_EMAIL}}` — support email
- `{{FRONTEND_URL}}` — production URL
- `{{LAST_UPDATED}}` — date in "Month DD, YYYY" format
- `{{JURISDICTION}}` — governing law jurisdiction (terms only)
