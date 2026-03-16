/**
 * components/guest-nudge.js — Guest-to-auth nudge banner.
 *
 * Shows a sticky banner after GUEST_NUDGE_AFTER guest actions,
 * encouraging the user to sign up.
 *
 * Expected DOM:
 *   <div id="guest-nudge" hidden>
 *     <span id="guest-nudge-text">Create a free account to save your progress.</span>
 *     <button id="guest-nudge-signup-btn">Sign up free</button>
 *     <button id="guest-nudge-close-btn">×</button>
 *   </div>
 *
 * DO NOT EDIT PER PROJECT.
 */

import auth from "../lib/auth.js";

const guestNudge = {
  /**
   * Initialize the nudge component. Call once after DOM is ready.
   * @param {{ onSignup?: () => void }} opts
   */
  init({ onSignup } = {}) {
    if (auth.isAuthenticated()) return;

    const nudge = document.getElementById("guest-nudge");
    const signupBtn = document.getElementById("guest-nudge-signup-btn");
    const closeBtn = document.getElementById("guest-nudge-close-btn");

    if (!nudge) return;

    window.addEventListener("guest:nudge", () => {
      nudge.hidden = false;
    });

    if (signupBtn) {
      signupBtn.addEventListener("click", () => {
        if (onSignup) {
          onSignup();
        } else {
          // Default: dispatch show-auth-modal event for auth-modal.js
          window.dispatchEvent(new CustomEvent("auth:show-modal"));
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        nudge.hidden = true;
      });
    }

    // Hide once authenticated
    auth.onLogin(() => {
      nudge.hidden = true;
    });
  },
};

export default guestNudge;
