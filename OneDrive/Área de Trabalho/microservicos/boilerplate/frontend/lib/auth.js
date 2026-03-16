/**
 * lib/auth.js — Auth state, JWT lifecycle, guest sessions.
 *
 * DO NOT EDIT PER PROJECT.
 *
 * Events dispatched:
 *   auth:login  — { detail: { user } }
 *   auth:logout — (no detail)
 *
 * Usage:
 *   import auth from "./lib/auth.js";
 *   await auth.init();          // call once on page load
 *   const user = auth.getUser();
 *   auth.onLogin(cb);
 */

import api from "./api.js";
import config from "../config.js";

const TOKEN_KEY = "access_token";
const USER_KEY = "auth_user";
const GUEST_KEY = "guest_session_id";
const GUEST_ACTIONS_KEY = "guest_action_count";

let _user = null;
let _initialized = false;

// ── Internal helpers ──────────────────────────────────────────────────

function _saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function _clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  _user = null;
}

function _saveUser(user) {
  _user = user;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function _loadCachedUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (raw) {
    try { _user = JSON.parse(raw); } catch (_) {}
  }
}

function _emit(eventName, detail = null) {
  const event = detail
    ? new CustomEvent(eventName, { detail })
    : new Event(eventName);
  window.dispatchEvent(event);
}

// ── Guest session ─────────────────────────────────────────────────────

function _ensureGuestSession() {
  if (!config.ENABLE_GUEST_SESSIONS) return null;
  let id = localStorage.getItem(GUEST_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(GUEST_KEY, id);
    localStorage.setItem(GUEST_ACTIONS_KEY, "0");
  }
  return id;
}

function _incrementGuestAction() {
  const count = parseInt(localStorage.getItem(GUEST_ACTIONS_KEY) || "0") + 1;
  localStorage.setItem(GUEST_ACTIONS_KEY, String(count));
  if (count >= config.GUEST_NUDGE_AFTER) {
    _emit("guest:nudge", { count });
  }
}

// ── Public API ────────────────────────────────────────────────────────

const auth = {
  /**
   * Initialize auth state. Call once on every page load.
   * Fetches /api/auth/me if a token is stored.
   */
  async init() {
    if (_initialized) return;
    _initialized = true;
    _loadCachedUser();

    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      try {
        const user = await api.get("/api/auth/me");
        _saveUser(user);
        _emit("auth:login", { user });
      } catch (_) {
        _clearToken();
      }
    } else if (config.ENABLE_GUEST_SESSIONS) {
      _ensureGuestSession();
    }
  },

  /**
   * Store a JWT and fetch the user profile.
   * Called after magic link verify or Google callback.
   */
  async loginWithToken(token) {
    _saveToken(token);
    const user = await api.get("/api/auth/me");
    _saveUser(user);

    // Migrate any guest session
    const guestId = localStorage.getItem(GUEST_KEY);
    if (guestId) {
      try {
        await api.post("/api/auth/guest/migrate", { guest_session_id: guestId });
      } catch (_) {}
      localStorage.removeItem(GUEST_KEY);
      localStorage.removeItem(GUEST_ACTIONS_KEY);
    }

    _emit("auth:login", { user });
    return user;
  },

  /** Sign out and clear all local auth state. */
  logout() {
    _clearToken();
    _emit("auth:logout");
  },

  /** Return the currently authenticated user object, or null. */
  getUser() {
    return _user;
  },

  /** Return true if the user is authenticated. */
  isAuthenticated() {
    return !!_user;
  },

  /** Return true if the user is an admin. */
  isAdmin() {
    return !!(_user && _user.is_admin);
  },

  /** Register a callback for auth:login events. */
  onLogin(cb) {
    window.addEventListener("auth:login", (e) => cb(e.detail?.user));
  },

  /** Register a callback for auth:logout events. */
  onLogout(cb) {
    window.addEventListener("auth:logout", cb);
  },

  /**
   * Track a guest action. Emits guest:nudge after GUEST_NUDGE_AFTER actions.
   * No-op if the user is authenticated.
   */
  trackGuestAction() {
    if (_user) return;
    _incrementGuestAction();
  },

  /** Return the current guest session ID, or null if authenticated. */
  getGuestSessionId() {
    if (_user) return null;
    return localStorage.getItem(GUEST_KEY);
  },

  /**
   * Handle the magic link verify flow (called from /auth/verify page).
   * Reads #token from the URL fragment, calls /api/auth/verify, then redirects.
   */
  async handleMagicLinkCallback(redirectTo = "/dashboard") {
    const hash = window.location.hash.slice(1);
    const params = new URLSearchParams(hash);
    const token = params.get("token");

    if (!token) throw new Error("No token found in URL");

    const data = await api.post("/api/auth/verify", { token });
    await auth.loginWithToken(data.access_token);
    window.location.href = redirectTo;
  },

  /**
   * Handle Google OAuth callback (called from /auth/google/callback page).
   * Reads ?code= from the query string, exchanges it, then redirects.
   */
  async handleGoogleCallback(redirectTo = "/dashboard") {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state") || "";

    if (!code) throw new Error("No code found in URL");

    const data = await api.post("/api/auth/google/callback", { code, state });
    await auth.loginWithToken(data.access_token);
    window.location.href = redirectTo;
  },
};

// Listen for 401 events from api.js
window.addEventListener("auth:logout", () => {
  _clearToken();
});

export default auth;
