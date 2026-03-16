/**
 * components/paywall.js — Paywall component.
 *
 * Listens for the "subscription:paywall-shown" event and renders
 * an upgrade prompt. Behaviour depends on config.PAYWALL_MODE:
 *   "modal"    — shows an in-page modal
 *   "redirect" — subscription.js already redirected; this is a no-op
 *
 * Expected DOM (create once in your layout):
 *   <div id="paywall-modal" hidden>
 *     <h2 id="paywall-title">Upgrade to Pro</h2>
 *     <p id="paywall-description">...</p>
 *     <button id="paywall-upgrade-btn">Upgrade</button>
 *     <button id="paywall-close-btn">Not now</button>
 *   </div>
 *
 * DO NOT EDIT PER PROJECT.
 */

import config from "../config.js";
import subscription from "../lib/subscription.js";
import { allPlans } from "../plans.js";

let _modal, _title, _description, _upgradeBtn;

function _render(feature) {
  const paidPlans = allPlans().filter((p) => p.price > 0);
  const firstPaid = paidPlans[0];

  if (_title) _title.textContent = `Upgrade to ${firstPaid?.name ?? "Pro"}`;
  if (_description)
    _description.textContent = `Unlock ${feature} and more with the ${firstPaid?.name ?? "Pro"} plan.`;
  if (_upgradeBtn && firstPaid) {
    _upgradeBtn.dataset.planKey = firstPaid.key;
  }
}

const paywall = {
  init() {
    if (config.PAYWALL_MODE !== "modal") return;

    _modal = document.getElementById("paywall-modal");
    _title = document.getElementById("paywall-title");
    _description = document.getElementById("paywall-description");
    _upgradeBtn = document.getElementById("paywall-upgrade-btn");
    const closeBtn = document.getElementById("paywall-close-btn");

    if (_upgradeBtn) {
      _upgradeBtn.addEventListener("click", async () => {
        const planKey = _upgradeBtn.dataset.planKey ?? "pro";
        await subscription.upgrade(planKey);
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", () => paywall.hide());

    window.addEventListener("subscription:paywall-shown", (e) => {
      _render(e.detail?.feature ?? "this feature");
      paywall.show();
    });
  },

  show() {
    if (_modal) _modal.hidden = false;
  },

  hide() {
    if (_modal) _modal.hidden = true;
  },
};

export default paywall;
