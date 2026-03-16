/**
 * components/toast.js — Queue-based toast notification system.
 *
 * Usage:
 *   import toast from "../components/toast.js";
 *   toast.show("Saved!", "success");
 *   toast.show("Something went wrong", "error");
 *   toast.show("FYI", "info");
 *
 * Automatically injects a #toast-container into <body> if not present.
 *
 * DO NOT EDIT PER PROJECT.
 */

const DURATION = 3500; // ms

let _container = null;
const _queue = [];
let _showing = false;

function _getContainer() {
  if (_container) return _container;

  _container = document.getElementById("toast-container");
  if (!_container) {
    _container = document.createElement("div");
    _container.id = "toast-container";
    _container.style.cssText = [
      "position:fixed",
      "bottom:24px",
      "right:24px",
      "display:flex",
      "flex-direction:column",
      "gap:8px",
      "z-index:9999",
      "max-width:320px",
    ].join(";");
    document.body.appendChild(_container);
  }
  return _container;
}

function _colorFor(type) {
  return { success: "#22c55e", error: "#ef4444", info: "#3b82f6" }[type] ?? "#111";
}

function _processQueue() {
  if (_showing || _queue.length === 0) return;
  _showing = true;

  const { message, type } = _queue.shift();
  const container = _getContainer();

  const el = document.createElement("div");
  el.style.cssText = [
    `background:${_colorFor(type)}`,
    "color:#fff",
    "padding:10px 16px",
    "border-radius:6px",
    "font-size:14px",
    "box-shadow:0 2px 8px rgba(0,0,0,.2)",
    "opacity:0",
    "transition:opacity .2s",
  ].join(";");
  el.textContent = message;

  container.appendChild(el);
  requestAnimationFrame(() => { el.style.opacity = "1"; });

  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => {
      el.remove();
      _showing = false;
      _processQueue();
    }, 200);
  }, DURATION);
}

const toast = {
  /**
   * Show a toast notification.
   * @param {string} message
   * @param {"success"|"error"|"info"} type
   */
  show(message, type = "info") {
    _queue.push({ message, type });
    _processQueue();
  },
};

export default toast;
