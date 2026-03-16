/**
 * components/auth-modal.js — Auth modal logic (email magic link + Google OAuth).
 *
 * This component is logic-only — it expects the host page to provide
 * the following DOM structure (or equivalent):
 *
 *   <div id="auth-modal" hidden>
 *     <form id="auth-form">
 *       <input id="auth-email" type="email" required />
 *       <button type="submit">Send magic link</button>
 *     </form>
 *     <button id="auth-google-btn">Sign in with Google</button>
 *     <p id="auth-message"></p>
 *     <button id="auth-modal-close">×</button>
 *   </div>
 *
 * Events dispatched:
 *   auth:login — when the user successfully authenticates
 *
 * DO NOT EDIT PER PROJECT.
 */

import api from "../lib/api.js";
import config from "../config.js";

let _modal, _form, _emailInput, _message, _googleBtn;

function _show(msg = "", isError = false) {
  if (_message) {
    _message.textContent = msg;
    _message.style.color = isError ? "red" : "green";
  }
}

async function _handleMagicLink(e) {
  e.preventDefault();
  const email = _emailInput.value.trim();
  if (!email) return;

  try {
    _show("Sending magic link…");
    await api.post("/api/auth/magic-link", { email });
    _show("Check your email for the sign-in link.");
    _form.reset();
  } catch (err) {
    _show(err.message, true);
  }
}

async function _handleGoogle() {
  try {
    const { url } = await api.get("/api/auth/google");
    window.location.href = url;
  } catch (err) {
    _show(err.message, true);
  }
}

const authModal = {
  /**
   * Initialize the modal component. Call once after the DOM is ready.
   */
  init() {
    _modal = document.getElementById("auth-modal");
    _form = document.getElementById("auth-form");
    _emailInput = document.getElementById("auth-email");
    _message = document.getElementById("auth-message");
    _googleBtn = document.getElementById("auth-google-btn");
    const closeBtn = document.getElementById("auth-modal-close");

    if (_form) _form.addEventListener("submit", _handleMagicLink);
    if (_googleBtn) {
      if (config.GOOGLE_CLIENT_ID) {
        _googleBtn.addEventListener("click", _handleGoogle);
      } else {
        _googleBtn.hidden = true;
      }
    }
    if (closeBtn) closeBtn.addEventListener("click", () => authModal.hide());
  },

  show() {
    if (_modal) _modal.hidden = false;
    if (_emailInput) _emailInput.focus();
    _show("");
  },

  hide() {
    if (_modal) _modal.hidden = true;
    _show("");
  },
};

export default authModal;
