/**
 * app/static/js/compare.js
 *
 * Powers the car comparison page.
 * - Highlights the best value in each numeric row (green = best)
 * - Scores each car overall and shows a winner badge
 * - Handles adding / removing cars from the tray
 * - Exposes the comparison table as a printable view
 */

(function () {
  'use strict';

  /* ── Row definitions: which spec rows to highlight and how ── */
  const SCORED_ROWS = [
    { key: 'price',      label: 'Price',       prefer: 'low',  weight: 3 },
    { key: 'mileage',    label: 'Mileage',     prefer: 'low',  weight: 3 },
    { key: 'year',       label: 'Year',        prefer: 'high', weight: 2 },
    { key: 'horsepower', label: 'Horsepower',  prefer: 'high', weight: 1 },
  ];

  /* ── Read car data attributes from the table ── */
  function readCarData(col) {
    const data = {};
    col.querySelectorAll('[data-spec]').forEach(cell => {
      data[cell.dataset.spec] = cell.dataset.value || cell.textContent.trim();
    });
    return data;
  }

  /* ── Parse a numeric value from a formatted string ── */
  function parseNum(str) {
    if (!str) return null;
    const n = parseFloat(String(str).replace(/[^0-9.]/g, ''));
    return isNaN(n) ? null : n;
  }

  /* ── Score each car column: returns array of total scores ── */
  function scoreColumns(cols) {
    const carData = cols.map(readCarData);
    const scores  = new Array(cols.length).fill(0);

    SCORED_ROWS.forEach(row => {
      const vals = carData.map(d => parseNum(d[row.key]));
      if (vals.every(v => v === null)) return;

      const validVals = vals.filter(v => v !== null);
      const best = row.prefer === 'low' ? Math.min(...validVals) : Math.max(...validVals);

      vals.forEach((v, i) => {
        if (v !== null && v === best) scores[i] += row.weight;
      });
    });

    return scores;
  }

  /* ── Highlight best / worst cells in numeric rows ── */
  function highlightRows(cols) {
    /* Find all spec rows that exist across columns */
    const specKeys = new Set();
    cols[0]?.querySelectorAll('[data-spec]').forEach(c => specKeys.add(c.dataset.spec));

    specKeys.forEach(key => {
      const cells = cols.map(col => col.querySelector(`[data-spec="${key}"]`));
      if (!cells.every(Boolean)) return;

      const vals = cells.map(c => parseNum(c.dataset.value || c.textContent));
      if (vals.every(v => v === null)) return;

      const validVals = vals.filter(v => v !== null);
      if (validVals.length < 2) return;

      const row = SCORED_ROWS.find(r => r.key === key);
      if (!row) return;

      const best  = row.prefer === 'low' ? Math.min(...validVals) : Math.max(...validVals);
      const worst = row.prefer === 'low' ? Math.max(...validVals) : Math.min(...validVals);

      cells.forEach((cell, i) => {
        if (vals[i] === null) return;
        cell.classList.remove('compare-best', 'compare-worst');
        if (vals[i] === best && validVals.length > 1) {
          cell.classList.add('compare-best');
        } else if (vals[i] === worst && validVals.length > 1) {
          cell.classList.add('compare-worst');
        }
      });
    });
  }

  /* ── Inject winner badges ── */
  function injectWinnerBadges(cols) {
    const scores = scoreColumns(cols);
    const maxScore = Math.max(...scores);

    /* Remove old badges */
    document.querySelectorAll('.compare-winner-badge').forEach(el => el.remove());

    if (maxScore === 0) return;

    cols.forEach((col, i) => {
      const header = col.querySelector('.compare-car-header');
      if (!header) return;

      /* Remove old score */
      header.querySelector('.compare-score-bar')?.remove();

      const pct = Math.round((scores[i] / maxScore) * 100);

      /* Score bar */
      const bar = document.createElement('div');
      bar.className = 'compare-score-bar';
      bar.innerHTML = `
        <div class="compare-score-track">
          <div class="compare-score-fill" style="width:${pct}%"></div>
        </div>
        <span class="compare-score-label">${scores[i]} pts</span>`;
      header.appendChild(bar);

      if (scores[i] === maxScore && cols.length > 1) {
        const badge = document.createElement('span');
        badge.className = 'compare-winner-badge';
        badge.innerHTML = '<i class="fa-solid fa-trophy" aria-hidden="true"></i> Best Value';
        header.prepend(badge);
      }
    });
  }

  /* ── Remove a car from the compare page ── */
  function bindRemoveButtons() {
    document.querySelectorAll('[data-remove-compare]').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = Number(btn.dataset.removeCompare);
        if (window.compareManager) window.compareManager.toggle(id, '');
        /* Rebuild URL and reload */
        const url = new URL(window.location.href);
        const ids = url.searchParams.getAll('ids').filter(i => i !== String(id));
        url.searchParams.delete('ids');
        ids.forEach(i => url.searchParams.append('ids', i));
        window.location.href = url.toString();
      });
    });
  }

  /* ── Print helper ── */
  const printBtn = document.getElementById('compare-print-btn');
  if (printBtn) {
    printBtn.addEventListener('click', () => window.print());
  }

  /* ── Init ── */
  function init() {
    const cols = [...document.querySelectorAll('.compare-col')];
    if (cols.length < 2) return;

    highlightRows(cols);
    injectWinnerBadges(cols);
    bindRemoveButtons();
  }

  document.addEventListener('DOMContentLoaded', init);

})();