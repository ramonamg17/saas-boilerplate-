/**
 * lib/subscription.js — Subscription state and paywall gating.
 *
 * DO NOT EDIT PER PROJECT.
 *
 * Events dispatched:
 *   subscription:paywall-shown — { detail: { feature } }
 *   subscription:upgraded      — { detail: { plan } }
 *
 * Usage:
 *   import subscription from "./lib/subscription.js";
 *   subscription.gate("feature-name"); // blocks or redirects
 *   const status = await subscription.getStatus();
 */

import api from "./api.js";
import config from "../config.js";
import { getPlan } from "../plans.js";

let _status = null;

// ── Internal helpers ──────────────────────────────────────────────────

function _emit(eventName, detail = null) {
  const event = detail
    ? new CustomEvent(eventName, { detail })
    : new Event(eventName);
  window.dispatchEvent(event);
}

// ── Public API ────────────────────────────────────────────────────────

const subscription = {
  /**
   * Fetch and cache the current user's billing status.
   * @returns {Promise<object>}
   */
  async getStatus(force = false) {
    if (_status && !force) return _status;
    _status = await api.get("/api/billing/status");
    return _status;
  },

  /**
   * Return the cached plan key (or "free").
   */
  getPlanKey() {
    return _status?.plan ?? "free";
  },

  /**
   * Return true if the user has an active or trialing subscription.
   */
  isActive() {
    const s = _status?.subscription_status;
    return s === "active" || s === "trialing";
  },

  /**
   * Gate access to a feature.
   * If the user is on a plan that lacks the feature, show a paywall.
   *
   * Paywall behaviour is determined by config.PAYWALL_MODE:
   *   "modal"    — dispatches "subscription:paywall-shown" (UI component listens)
   *   "redirect" — redirects to /dashboard/plan
   *
   * @param {string} feature — arbitrary feature key for tracking
   * @param {string} [requiredPlan="pro"] — minimum plan key required
   * @returns {boolean} — true if access is granted
   */
  gate(feature, requiredPlan = "pro") {
    const currentKey = subscription.getPlanKey();
    const planKeys = ["free", "pro"]; // order matters: lower index = lower tier
    const currentIdx = planKeys.indexOf(currentKey);
    const requiredIdx = planKeys.indexOf(requiredPlan);

    if (currentIdx >= requiredIdx) return true;

    _emit("subscription:paywall-shown", { feature });

    if (config.PAYWALL_MODE === "redirect") {
      window.location.href = `/dashboard/plan?feature=${encodeURIComponent(feature)}`;
    }

    return false;
  },

  /**
   * Open the Stripe Checkout or Elements flow for a given plan.
   * @param {string} planKey
   */
  async upgrade(planKey) {
    if (config.BILLING_MODE === "checkout") {
      const { url } = await api.post("/api/billing/checkout", { plan_key: planKey });
      window.location.href = url;
    } else {
      // elements — return client_secret to the caller for Stripe.js
      const { client_secret } = await api.post("/api/billing/payment-intent", { plan_key: planKey });
      _emit("subscription:upgraded", { plan: getPlan(planKey), client_secret });
      return client_secret;
    }
  },

  /**
   * Open the Stripe Customer Portal.
   */
  async openPortal() {
    const { url } = await api.post("/api/billing/portal", {});
    window.location.href = url;
  },

  /**
   * Cancel the current subscription.
   * @param {string} reason
   * @param {string} feedback
   */
  async cancel(reason = "", feedback = "") {
    return api.post("/api/billing/cancel", { reason, feedback });
  },

  /**
   * Reactivate a cancelled subscription.
   */
  async reactivate() {
    return api.post("/api/billing/reactivate", {});
  },
};

export default subscription;
