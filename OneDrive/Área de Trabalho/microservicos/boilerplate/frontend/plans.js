/**
 * plans.js — Frontend mirror of backend/plans.py.
 *
 * EDIT PER PROJECT: set real Stripe price IDs and adjust plan details.
 */

const PLANS = {
  free: {
    key: "free",
    name: "Free",
    price: 0,
    stripePriceId: "",              // EDIT PER PROJECT
    trialDays: 0,
    limits: {
      requestsPerHour: 20,
    },
    features: [
      "20 requests/hour",
      "Basic features",
    ],
  },
  pro: {
    key: "pro",
    name: "Pro",
    price: 19,
    stripePriceId: "price_placeholder_pro",  // EDIT PER PROJECT
    trialDays: 14,
    limits: {
      requestsPerHour: 500,
    },
    features: [
      "500 requests/hour",
      "All features",
      "Priority support",
      `${14}-day free trial`,
    ],
  },
};

/**
 * Return a plan by key, falling back to "free".
 * @param {string} key
 * @returns {object}
 */
function getPlan(key) {
  return PLANS[key] ?? PLANS.free;
}

/**
 * Return all plans as an array (preserves insertion order).
 * @returns {object[]}
 */
function allPlans() {
  return Object.values(PLANS);
}

export { PLANS, getPlan, allPlans };
