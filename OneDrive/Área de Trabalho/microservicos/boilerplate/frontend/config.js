/**
 * config.js — Frontend mirror of backend/config.py.
 *
 * Lines marked // EDIT PER PROJECT should be updated for each new project.
 * Import this file wherever runtime config is needed.
 */

const config = {
  // ── Application identity ─────────────────────────────────────
  APP_NAME: "My SaaS App",           // EDIT PER PROJECT
  FRONTEND_URL: window.location.origin,
  SUPPORT_EMAIL: "support@example.com",  // EDIT PER PROJECT

  // ── API ──────────────────────────────────────────────────────
  API_BASE_URL: "http://localhost:8000",  // EDIT PER PROJECT (prod: Railway URL)

  // ── Stripe ───────────────────────────────────────────────────
  STRIPE_PUBLISHABLE_KEY: "pk_test_placeholder",  // EDIT PER PROJECT

  // "checkout" | "elements"  — must match backend BILLING_MODE
  BILLING_MODE: "checkout",   // EDIT PER PROJECT

  // ── Feature flags ────────────────────────────────────────────
  // "modal" | "redirect"
  PAYWALL_MODE: "modal",

  ENABLE_GUEST_SESSIONS: true,
  GUEST_NUDGE_AFTER: 3,

  // ── Google OAuth ─────────────────────────────────────────────
  // Leave GOOGLE_CLIENT_ID empty to hide the "Sign in with Google" button
  GOOGLE_CLIENT_ID: "",              // EDIT PER PROJECT
};

export default config;
