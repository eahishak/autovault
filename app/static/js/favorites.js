/**
 * app/static/js/favorites.js
 *
 * Handles heart-button favorite toggling across all pages.
 * - Optimistic UI: flips state instantly, reverts on failure
 * - Single /api/favorites POST endpoint for all toggle actions
 * - Exposes window.FavoritesModule.bindAll() so filters.js can
 *   re-attach listeners after the car grid is replaced via AJAX
 */

(function () {
  'use strict';

  const API_URL  = '/api/favorites';
  const ACTIVE   = 'active';

  /* ── CSRF token (Flask-WTF meta or cookie fallback) ── */
  function getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  /* ── Optimistically toggle a button's visual state ── */
  function setActive(btn, active) {
    btn.classList.toggle(ACTIVE, active);
    btn.setAttribute('aria-pressed', String(active));
    btn.setAttribute('aria-label', active ? 'Remove from saved' : 'Save car');

    const icon = btn.querySelector('i');
    if (!icon) return;
    icon.classList.toggle('fa-solid',  active);
    icon.classList.toggle('fa-regular', !active);
  }

  /* ── Show a lightweight toast without re-importing the base helper ── */
  function toast(msg, category = 'info') {
    const stack = document.querySelector('.toast-stack');
    if (!stack) return;
    const el = document.createElement('div');
    el.className = `toast toast--${category}`;
    el.setAttribute('data-toast', '');
    const iconMap = {
      success: 'fa-circle-check',
      danger:  'fa-circle-xmark',
      warning: 'fa-triangle-exclamation',
      info:    'fa-circle-info',
    };
    el.innerHTML = `
      <span class="toast-icon"><i class="fa-solid ${iconMap[category] || iconMap.info}"></i></span>
      <span class="toast-msg">${msg}</span>
      <button class="toast-close" aria-label="Dismiss" onclick="this.closest('[data-toast]').remove()">
        <i class="fa-solid fa-xmark"></i>
      </button>`;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add('toast--out');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, 4000);
  }

  /* ── Core toggle handler ── */
  async function handleToggle(e) {
    e.preventDefault();
    e.stopPropagation();

    const btn   = e.currentTarget;
    const carId = Number(btn.dataset.favId);

    if (!carId) return;

    /* Redirect to login if not authenticated */
    if (btn.dataset.authRequired === 'true' || !document.body.dataset.userId) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      return;
    }

    const wasActive = btn.classList.contains(ACTIVE);

    /* Optimistic update */
    setActive(btn, !wasActive);

    /* Disable during request */
    btn.disabled = true;

    try {
      const res = await fetch(API_URL, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken':  getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ car_id: carId }),
      });

      if (res.status === 401) {
        setActive(btn, wasActive);          // revert
        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const isFav = data.favorited === true;

      /* Confirm final state from server */
      setActive(btn, isFav);
      toast(isFav ? 'Saved to your garage.' : 'Removed from saved.', 'success');

      /* Keep all buttons for same car in sync (e.g. card + detail page) */
      document.querySelectorAll(`[data-fav-id="${carId}"]`).forEach(other => {
        if (other !== btn) setActive(other, isFav);
      });

    } catch (err) {
      /* Revert on any error */
      setActive(btn, wasActive);
      toast('Could not update saved cars. Please try again.', 'danger');
      console.error('[favorites] toggle failed:', err);
    } finally {
      btn.disabled = false;
    }
  }

  /* ── Bind a single button ── */
  function bindBtn(btn) {
    /* Avoid double-binding */
    if (btn.dataset.favBound === '1') return;
    btn.dataset.favBound = '1';
    btn.addEventListener('click', handleToggle);
  }

  /* ── Bind all favorite buttons on the page ── */
  function bindAll() {
    document.querySelectorAll('[data-fav-id]').forEach(bindBtn);
  }

  /* ── Watch for dynamically injected buttons (MutationObserver) ── */
  const observer = new MutationObserver(mutations => {
    mutations.forEach(m => {
      m.addedNodes.forEach(node => {
        if (node.nodeType !== 1) return;
        if (node.matches('[data-fav-id]')) bindBtn(node);
        node.querySelectorAll?.('[data-fav-id]').forEach(bindBtn);
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });

  /* ── Init ── */
  document.addEventListener('DOMContentLoaded', bindAll);

  /* ── Public API ── */
  window.FavoritesModule = { bindAll };

})();