/**
 * app/static/js/search.js
 *
 * Live autocomplete for the navbar and hero search inputs.
 * Hits /api/search?q=... and renders a suggestion dropdown.
 * Full keyboard navigation (arrow keys, Enter, Escape).
 * Exposes window.SearchSuggest.attach(inputEl) for the hero input.
 */

(function () {
  'use strict';

  const API_URL    = '/api/search';
  const DEBOUNCE   = 280;
  const MIN_CHARS  = 2;
  const MAX_SHOWN  = 8;

  /* ── Build or find the suggestion list for an input ── */
  function getDropdown(input) {
    const id = input.getAttribute('aria-controls');
    return id ? document.getElementById(id) : null;
  }

  /* ── Escape HTML to prevent XSS in suggestions ── */
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ── Highlight matching query text inside a suggestion string ── */
  function highlight(text, query) {
    if (!query) return esc(text);
    const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return esc(text).replace(re, '<mark>$1</mark>');
  }

  /* ── Render suggestion items into the dropdown ── */
  function renderSuggestions(dropdown, results, query) {
    if (!results || results.length === 0) {
      dropdown.hidden = true;
      return;
    }

    dropdown.innerHTML = results.slice(0, MAX_SHOWN).map((item, i) => `
      <div
        class="search-suggestion-item"
        role="option"
        id="suggestion-${i}"
        data-href="${esc(item.url)}"
        data-value="${esc(item.label)}"
        tabindex="-1"
      >
        <i class="fa-solid ${esc(item.icon || 'fa-car')}" aria-hidden="true"></i>
        <span>${highlight(item.label, query)}</span>
        ${item.sublabel ? `<span style="margin-left:auto; font-size:.72rem; color:var(--text-muted)">${esc(item.sublabel)}</span>` : ''}
      </div>
    `).join('');

    dropdown.hidden = false;

    /* Bind click on each item */
    dropdown.querySelectorAll('.search-suggestion-item').forEach(el => {
      el.addEventListener('mousedown', e => {
        e.preventDefault();   // prevent blur before click
        window.location.href = el.dataset.href;
      });
    });
  }

  /* ── Core attach function ── */
  function attach(input) {
    if (!input || input.dataset.searchBound === '1') return;
    input.dataset.searchBound = '1';

    const dropdown = getDropdown(input);
    if (!dropdown) return;

    let timer       = null;
    let activeIndex = -1;
    let controller  = null;

    function getItems() {
      return [...dropdown.querySelectorAll('.search-suggestion-item')];
    }

    function setActive(idx) {
      const items = getItems();
      items.forEach((el, i) => {
        el.classList.toggle('active', i === idx);
        el.setAttribute('aria-selected', String(i === idx));
      });
      activeIndex = idx;
      if (items[idx]) {
        input.setAttribute('aria-activedescendant', items[idx].id);
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    }

    async function fetchSuggestions(q) {
      if (controller) controller.abort();
      controller = new AbortController();

      try {
        const res = await fetch(`${API_URL}?q=${encodeURIComponent(q)}&limit=${MAX_SHOWN}`, {
          signal: controller.signal,
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!res.ok) return;
        const data = await res.json();
        renderSuggestions(dropdown, data.results, q);
        activeIndex = -1;
      } catch (err) {
        if (err.name !== 'AbortError') {
          dropdown.hidden = true;
        }
      }
    }

    function close() {
      dropdown.hidden = true;
      activeIndex = -1;
      input.removeAttribute('aria-activedescendant');
    }

    /* Input event — debounced fetch */
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < MIN_CHARS) { close(); return; }
      timer = setTimeout(() => fetchSuggestions(q), DEBOUNCE);
    });

    /* Keyboard navigation */
    input.addEventListener('keydown', e => {
      const items = getItems();
      if (dropdown.hidden || items.length === 0) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setActive(Math.min(activeIndex + 1, items.length - 1));
          break;

        case 'ArrowUp':
          e.preventDefault();
          setActive(Math.max(activeIndex - 1, -1));
          if (activeIndex === -1) input.removeAttribute('aria-activedescendant');
          break;

        case 'Enter':
          if (activeIndex >= 0 && items[activeIndex]) {
            e.preventDefault();
            window.location.href = items[activeIndex].dataset.href;
          }
          break;

        case 'Escape':
          close();
          break;

        case 'Tab':
          close();
          break;
      }
    });

    /* Close on blur (slight delay so mousedown fires first) */
    input.addEventListener('blur', () => {
      setTimeout(close, 150);
    });

    /* Reopen on focus if there's a value */
    input.addEventListener('focus', () => {
      const q = input.value.trim();
      if (q.length >= MIN_CHARS) fetchSuggestions(q);
    });
  }

  /* ── Auto-attach to known inputs on DOMContentLoaded ── */
  document.addEventListener('DOMContentLoaded', () => {
    const navInput = document.getElementById('nav-search-input');
    if (navInput) attach(navInput);
  });

  /* ── Public API ── */
  window.SearchSuggest = { attach };

})();