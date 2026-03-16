/**
 * lib/admin.js — Admin API helpers.
 *
 * DO NOT EDIT PER PROJECT.
 *
 * All methods require the current user to be an admin.
 */

import api from "./api.js";

const admin = {
  /**
   * List users with optional filters.
   * @param {{ page?: number, perPage?: number, plan?: string, search?: string }} opts
   */
  async listUsers({ page = 1, perPage = 50, plan, search } = {}) {
    const params = new URLSearchParams({ page, per_page: perPage });
    if (plan) params.set("plan", plan);
    if (search) params.set("search", search);
    return api.get(`/api/admin/users?${params}`);
  },

  /**
   * Get a single user's details.
   * @param {number} userId
   */
  async getUser(userId) {
    return api.get(`/api/admin/users/${userId}`);
  },

  /**
   * Override a user's plan.
   * @param {number} userId
   * @param {string} planKey
   */
  async overridePlan(userId, planKey) {
    return api.post(`/api/admin/users/${userId}/plan`, { plan_key: planKey });
  },

  /**
   * Start an impersonation session for a user.
   * Returns a JWT that can be used to act as the target user.
   * @param {number} userId
   */
  async impersonate(userId) {
    return api.post(`/api/admin/users/${userId}/impersonate`, {});
  },

  /**
   * Fetch platform statistics.
   */
  async getStats() {
    return api.get("/api/admin/stats");
  },
};

export default admin;
