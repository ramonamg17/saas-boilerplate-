/**
 * lib/api.js — Fetch wrapper with automatic JWT header injection.
 *
 * All frontend HTTP calls should go through this module.
 * On 401, emits a global "auth:logout" event so auth.js can clean up.
 *
 * DO NOT EDIT PER PROJECT.
 */

import config from "../config.js";

const BASE = config.API_BASE_URL;

/**
 * Core fetch wrapper.
 * @param {string} path — API path, e.g. "/api/auth/me"
 * @param {RequestInit} options — standard fetch options
 * @returns {Promise<any>} — parsed JSON response
 */
async function request(path, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("auth:logout"));
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }

  // 204 No Content
  if (response.status === 204) return null;

  return response.json();
}

const api = {
  get: (path, options = {}) => request(path, { ...options, method: "GET" }),
  post: (path, body, options = {}) =>
    request(path, { ...options, method: "POST", body: JSON.stringify(body) }),
  patch: (path, body, options = {}) =>
    request(path, { ...options, method: "PATCH", body: JSON.stringify(body) }),
  delete: (path, body, options = {}) =>
    request(path, { ...options, method: "DELETE", body: JSON.stringify(body) }),
};

export default api;
