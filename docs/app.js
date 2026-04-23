/* ==========================================================
   AI Navigation Manifest — ROI Calculator & Interactions
   v1.0 · 2026-04-23
   ========================================================== */

(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  function fmtKRW(n) {
    if (!isFinite(n)) return '-';
    if (n >= 100000000) return (n / 100000000).toFixed(1) + '억 원';
    if (n >= 10000) return Math.round(n / 10000).toLocaleString() + '만 원';
    return Math.round(n).toLocaleString() + ' 원';
  }

  function fmtMonths(m) {
    if (!isFinite(m) || m <= 0) return '즉시';
    if (m < 1) return (m * 30).toFixed(0) + '일';
    if (m < 12) return m.toFixed(1) + '개월';
    return (m / 12).toFixed(1) + '년';
  }

  function calc() {
    const monthlyCount = +$('monthlyCount').value || 0;
    const tokensB = +$('baselineTokens').value || 0;
    const tokensM = +$('manifestTokens').value || 0;
    const price = +$('modelPrice').value || 0;
    const fx = +$('fxRate').value || 1400;
    const poc = +$('pocAmount').value || 0;

    // 월 토큰 비용(원) = 월 건수 × 건당 토큰 × 단가(USD/1M) × 환율
    const costB = (monthlyCount * tokensB * price * fx) / 1_000_000;
    const costM = (monthlyCount * tokensM * price * fx) / 1_000_000;
    const monthly = Math.max(0, costB - costM);
    const annual = monthly * 12;
    const payback = monthly > 0 ? poc / monthly : Infinity;
    const threeYear = annual * 3 - poc;

    $('outMonthly').textContent = fmtKRW(monthly);
    $('outAnnual').textContent = fmtKRW(annual);
    $('outPayback').textContent = fmtMonths(payback);
    $('outThreeYear').textContent = fmtKRW(threeYear);
  }

  // Bind input events
  ['monthlyCount', 'baselineTokens', 'manifestTokens', 'modelPrice', 'fxRate', 'pocAmount']
    .forEach(id => {
      const el = $(id);
      if (el) {
        el.addEventListener('input', calc);
        el.addEventListener('change', calc);
      }
    });

  // Initial calculation on load
  document.addEventListener('DOMContentLoaded', calc);

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href').slice(1);
      if (!id) return;
      const el = document.getElementById(id);
      if (!el) return;
      e.preventDefault();
      window.scrollTo({ top: el.offsetTop - 72, behavior: 'smooth' });
    });
  });
})();
