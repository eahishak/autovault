/**
 * app/static/js/image_gallery.js
 *
 * Powers the car detail image gallery.
 * - Prev / next navigation with keyboard arrow support
 * - Thumbnail strip sync + active highlight
 * - Touch swipe left / right on mobile
 * - Lazy preloading of adjacent images
 * - Smooth crossfade transition between images
 * - Reads window.GALLERY_IMAGES set by car_detail.html
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', init);

  function init() {
    const images = window.GALLERY_IMAGES;
    if (!Array.isArray(images) || images.length === 0) return;

    const mainImg   = document.getElementById('gallery-main-img');
    const prevBtn   = document.getElementById('gallery-prev');
    const nextBtn   = document.getElementById('gallery-next');
    const counter   = document.getElementById('gallery-counter');
    const thumbBtns = document.querySelectorAll('.gallery__thumb');

    if (!mainImg) return;

    let current = 0;
    let isTransitioning = false;

    /* ── Navigate to index ── */
    function goTo(idx, direction) {
      if (isTransitioning) return;
      if (idx < 0) idx = images.length - 1;
      if (idx >= images.length) idx = 0;
      if (idx === current) return;

      isTransitioning = true;

      /* Crossfade: fade out */
      mainImg.style.transition = 'opacity 180ms ease';
      mainImg.style.opacity    = '0';

      setTimeout(() => {
        mainImg.src = images[idx];
        mainImg.alt = `Vehicle photo ${idx + 1} of ${images.length}`;
        current = idx;

        /* Fade in */
        mainImg.style.opacity = '1';
        isTransitioning = false;

        updateCounter();
        updateThumbs();
        preloadAdjacent();
      }, 180);
    }

    function updateCounter() {
      if (counter) {
        counter.textContent = `${current + 1} / ${images.length}`;
        counter.setAttribute('aria-label', `Photo ${current + 1} of ${images.length}`);
      }
    }

    function updateThumbs() {
      thumbBtns.forEach((btn, i) => {
        const isActive = i === current;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', String(isActive));
      });

      /* Scroll active thumb into view */
      const activeThumb = thumbBtns[current];
      if (activeThumb) {
        activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
      }
    }

    /* Preload previous and next images for snappy nav */
    function preloadAdjacent() {
      const indices = [
        (current - 1 + images.length) % images.length,
        (current + 1) % images.length,
      ];
      indices.forEach(i => {
        if (i !== current) {
          const img = new Image();
          img.src = images[i];
        }
      });
    }

    /* ── Event listeners ── */
    if (prevBtn) prevBtn.addEventListener('click', () => goTo(current - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goTo(current + 1));

    thumbBtns.forEach((btn, i) => {
      btn.addEventListener('click', () => goTo(i));
    });

    /* Keyboard navigation (only when gallery area is focused) */
    const galleryEl = document.getElementById('gallery');
    if (galleryEl) {
      galleryEl.setAttribute('tabindex', '0');
      galleryEl.addEventListener('keydown', e => {
        if (e.key === 'ArrowLeft')  { e.preventDefault(); goTo(current - 1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); goTo(current + 1); }
        if (e.key === 'Home')       { e.preventDefault(); goTo(0); }
        if (e.key === 'End')        { e.preventDefault(); goTo(images.length - 1); }
      });
    }

    /* Touch swipe support */
    let touchStartX = 0;
    let touchStartY = 0;

    mainImg.addEventListener('touchstart', e => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    mainImg.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].screenX - touchStartX;
      const dy = e.changedTouches[0].screenY - touchStartY;

      /* Only trigger if horizontal swipe is dominant (not a scroll) */
      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
        if (dx < 0) goTo(current + 1);  // swipe left  → next
        else        goTo(current - 1);  // swipe right → prev
      }
    }, { passive: true });

    /* Prevent default drag on image (avoids ghost drag artifacts) */
    mainImg.addEventListener('dragstart', e => e.preventDefault());

    /* ── Init: preload first adjacent pair ── */
    preloadAdjacent();
    updateCounter();
  }

})();