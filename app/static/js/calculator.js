/**
 * app/static/js/calculator.js
 *
 * Monthly payment calculator on the car detail page.
 * Uses the standard amortization formula:
 *   M = P * [r(1+r)^n] / [(1+r)^n - 1]
 *
 * Reads window.CAR_PRICE_CENTS set by car_detail.html.
 * Updates live as the user changes any input.
 */

(function () {
  'use strict';

  /* Wait for DOM */
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    const priceEl  = window.CAR_PRICE_CENTS;
    const downEl   = document.getElementById('calc-down');
    const aprEl    = document.getElementById('calc-apr');
    const termEl   = document.getElementById('calc-term');
    const output   = document.getElementById('calc-output');

    if (!downEl || !aprEl || !termEl || !output) return;
    if (typeof priceEl === 'undefined') return;

    function calculate() {
      const priceDollars = priceEl / 100;
      const down         = Math.max(0, parseFloat(downEl.value)  || 0);
      const aprPct       = Math.max(0, parseFloat(aprEl.value)   || 0);
      const termMonths   = Math.max(1, parseInt(termEl.value, 10) || 60);

      const principal = priceDollars - down;

      if (principal <= 0) {
        output.textContent = '$0 / mo';
        updateBreakdown(0, 0, 0);
        return;
      }

      const monthlyRate = aprPct / 100 / 12;
      let monthly;

      if (monthlyRate === 0) {
        monthly = principal / termMonths;
      } else {
        const factor = Math.pow(1 + monthlyRate, termMonths);
        monthly = principal * (monthlyRate * factor) / (factor - 1);
      }

      const totalPaid    = monthly * termMonths;
      const totalInterest = totalPaid - principal;

      output.textContent = formatCurrency(monthly) + ' /mo';
      updateBreakdown(principal, totalInterest, totalPaid);
      animatePulse(output);
    }

    function updateBreakdown(principal, interest, total) {
      setElText('calc-principal', formatCurrency(principal));
      setElText('calc-interest',  formatCurrency(interest));
      setElText('calc-total',     formatCurrency(total));

      /* Update donut chart if present */
      const canvas = document.getElementById('calc-donut');
      if (canvas && total > 0) drawDonut(canvas, principal, interest);
    }

    function setElText(id, val) {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    }

    function formatCurrency(n) {
      if (isNaN(n) || !isFinite(n)) return '$—';
      return '$' + Math.round(n).toLocaleString('en-US');
    }

    /* Subtle scale pulse on output change */
    function animatePulse(el) {
      el.style.transition = 'none';
      el.style.transform  = 'scale(1.06)';
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.style.transition = 'transform 200ms ease-out';
          el.style.transform  = 'scale(1)';
        });
      });
    }

    /* Simple canvas donut showing principal vs interest split */
    function drawDonut(canvas, principal, interest) {
      const ctx  = canvas.getContext('2d');
      const W    = canvas.width;
      const H    = canvas.height;
      const cx   = W / 2;
      const cy   = H / 2;
      const r    = Math.min(W, H) / 2 - 6;
      const inner = r * 0.58;
      const total = principal + interest;

      ctx.clearRect(0, 0, W, H);

      /* Principal arc (brand red) */
      const principalAngle = (principal / total) * 2 * Math.PI;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + principalAngle);
      ctx.closePath();
      ctx.fillStyle = '#b91c1c';
      ctx.fill();

      /* Interest arc (muted) */
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, -Math.PI / 2 + principalAngle, -Math.PI / 2 + 2 * Math.PI);
      ctx.closePath();
      ctx.fillStyle = '#e7e5e4';
      ctx.fill();

      /* Hole (donut) */
      ctx.beginPath();
      ctx.arc(cx, cy, inner, 0, 2 * Math.PI);
      ctx.fillStyle = getComputedStyle(document.documentElement)
        .getPropertyValue('--bg-elevated').trim() || '#fff';
      ctx.fill();
    }

    /* Validate down payment doesn't exceed car price */
    downEl.addEventListener('input', () => {
      const max = (priceEl / 100) - 1;
      if (parseFloat(downEl.value) > max) downEl.value = Math.floor(max);
      calculate();
    });

    aprEl.addEventListener('input', calculate);
    termEl.addEventListener('change', calculate);

    /* Run on load */
    calculate();
  }

})();