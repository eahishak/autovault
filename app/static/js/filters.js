/**
 * app/static/js/filters.js
 *
 * Live AJAX filtering for the browse page.
 * Debounces form changes, hits /api/cars with current params,
 * and replaces the car grid without a full page reload.
 * Falls back gracefully to a full form submit if the API is unavailable.
 */

(function () {
  'use strict';

  const DEBOUNCE_MS  = 420;
  const API_ENDPOINT = '/api/cars';

  const grid    = document.getElementById('car-grid');
  const wrap    = document.getElementById('car-grid-wrap');
  const form    = document.getElementById('filter-form');
  const counter = document.querySelector('.browse-result-count');

  if (!form || !grid) return;

  let debounceTimer  = null;
  let activeRequest  = null;   // AbortController for in-flight fetch

  /* ── Serialize form to URLSearchParams ── */
  function serializeForm(f) {
    const params = new URLSearchParams();
    const data   = new FormData(f);
    for (const [key, val] of data.entries()) {
      if (val !== '') params.append(key, val);
    }
    // always keep page=1 on filter change
    params.set('page', '1');
    return params;
  }

  /* ── Push new URL state without reload ── */
  function pushState(params) {
    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.pushState({ params: params.toString() }, '', url);
  }

  /* ── Loading state ── */
  function setLoading(on) {
    wrap.classList.toggle('loading', on);
    form.querySelectorAll('input, select, button').forEach(el => {
      el.disabled = on;
    });
  }

  /* ── Render car cards from API response ── */
  function renderCards(html, total) {
    grid.innerHTML = html;

    if (counter) {
      const s = total === 1 ? '' : 's';
      counter.innerHTML = `<strong>${total.toLocaleString()}</strong> vehicle${s} found`;
    }

    /* Re-attach favorite listeners after DOM replacement */
    if (window.FavoritesModule) {
      window.FavoritesModule.bindAll();
    }

    /* Re-attach compare checkboxes */
    bindCompareCheckboxes();

    /* Announce to screen readers */
    const announce = document.getElementById('sr-live-region');
    if (announce) {
      announce.textContent = `${total} result${total === 1 ? '' : 's'} found.`;
    }
  }

  /* ── Empty state HTML ── */
  function emptyStateHtml() {
    return `
      <div class="empty-state">
        <div class="empty-state__icon"><i class="fa-solid fa-car-burst" aria-hidden="true"></i></div>
        <h3 class="empty-state__title">No results found</h3>
        <p class="empty-state__body">Try adjusting your filters or clearing the search term.</p>
        <a href="/browse" class="btn-primary">Clear All Filters</a>
      </div>`;
  }

  /* ── Main fetch ── */
  async function fetchResults(params) {
    if (activeRequest) activeRequest.abort();
    activeRequest = new AbortController();

    setLoading(true);

    try {
      const url = `${API_ENDPOINT}?${params.toString()}&format=html`;
      const res = await fetch(url, {
        signal: activeRequest.signal,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      if (data.html) {
        renderCards(data.html, data.total || 0);
      } else {
        grid.innerHTML = emptyStateHtml();
        if (counter) counter.innerHTML = '<strong>0</strong> vehicles found';
      }

      pushState(params);
    } catch (err) {
      if (err.name === 'AbortError') return;
      /* Network error — fall back to full page submit */
      form.submit();
    } finally {
      setLoading(false);
      activeRequest = null;
    }
  }

  /* ── Debounced handler ── */
  function onFormChange() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      fetchResults(serializeForm(form));
    }, DEBOUNCE_MS);
  }

  /* ── Bind form events ── */
  form.addEventListener('change', onFormChange);

  /* Range inputs fire 'input', not 'change', for live feedback */
  form.querySelectorAll('input[type="number"]').forEach(input => {
    input.addEventListener('input', onFormChange);
  });

  /* Prevent default submit — we always handle via AJAX */
  form.addEventListener('submit', e => {
    e.preventDefault();
    clearTimeout(debounceTimer);
    fetchResults(serializeForm(form));
  });

  /* ── Keyboard shortcut: / focuses the search input ── */
  document.addEventListener('keydown', e => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault();
      const searchInput = document.getElementById('nav-search-input');
      if (searchInput) searchInput.focus();
    }
  });

  /* ── Compare checkboxes ── */
  function bindCompareCheckboxes() {
    document.querySelectorAll('.compare-checkbox').forEach(cb => {
      cb.removeEventListener('change', onCompareChange);
      cb.addEventListener('change', onCompareChange);

      /* Restore checked state from compareManager */
      if (window.compareManager) {
        cb.checked = window.compareManager.ids().includes(Number(cb.dataset.compareId));
      }
    });
  }

  function onCompareChange(e) {
    const cb    = e.currentTarget;
    const id    = Number(cb.dataset.compareId);
    const title = cb.dataset.compareTitle || '';

    if (!window.compareManager) return;

    const ok = window.compareManager.toggle(id, title);
    if (!ok && cb.checked) {
      cb.checked = false;
      showMaxCompareToast();
    }
  }

  function showMaxCompareToast() {
    const stack = document.querySelector('.toast-stack');
    if (!stack) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast--warning';
    toast.setAttribute('data-toast', '');
    toast.innerHTML = `
      <span class="toast-icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
      <span class="toast-msg">You can compare up to 3 cars at a time.</span>
      <button class="toast-close" aria-label="Dismiss" onclick="this.closest('[data-toast]').remove()">
        <i class="fa-solid fa-xmark"></i>
      </button>`;
    stack.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('toast--out');
      toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, 4000);
  }

  /* ── Popstate: restore filters when user hits Back ── */
  window.addEventListener('popstate', e => {
    if (e.state && e.state.params) {
      const params = new URLSearchParams(e.state.params);
      /* Re-populate form fields from params */
      params.forEach((val, key) => {
        const el = form.querySelector(`[name="${key}"]`);
        if (el) {
          if (el.type === 'radio' || el.type === 'checkbox') {
            form.querySelectorAll(`[name="${key}"]`).forEach(r => {
              r.checked = r.value === val;
            });
          } else {
            el.value = val;
          }
        }
      });
      fetchResults(params);
    }
  });

  /* ── Inject a live-region for screen reader announcements ── */
  if (!document.getElementById('sr-live-region')) {
    const region = document.createElement('div');
    region.id = 'sr-live-region';
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    region.setAttribute('aria-atomic', 'true');
    region.className = 'sr-only';
    document.body.appendChild(region);
  }

  /* ── Init ── */
  bindCompareCheckboxes();

})();