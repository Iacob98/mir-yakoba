// Мир Якоба — public site behaviors: mobile menu, scroll reveal, reading progress.
// Loaded once in <head> (defer); re-initialized after htmx swaps via htmx:afterSettle.
(function () {
  'use strict';

  var hasIO = 'IntersectionObserver' in window;
  if (hasIO) document.documentElement.classList.add('has-reveal');

  function initMenu() {
    var toggle = document.getElementById('navToggle');
    var menu = document.getElementById('mobileNav');
    if (!toggle || !menu || toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('click', function () {
      var open = menu.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    menu.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  var observer = hasIO
    ? new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 })
    : null;

  function observeReveals() {
    if (!observer) return;
    var els = document.querySelectorAll('[data-reveal]:not(.is-observed)');
    els.forEach(function (el, i) {
      el.classList.add('is-observed');
      el.style.transitionDelay = Math.min(i, 6) * 60 + 'ms';
      observer.observe(el);
    });
  }

  // JS fallback for browsers without CSS scroll-driven animations.
  function initProgress() {
    var bar = document.getElementById('progress');
    if (!bar || bar.dataset.bound) return;
    if (window.CSS && CSS.supports('animation-timeline: scroll()')) return;
    bar.dataset.bound = '1';
    function update() {
      var doc = document.documentElement;
      var max = doc.scrollHeight - window.innerHeight;
      bar.style.width = (max > 0 ? Math.min(1, window.scrollY / max) * 100 : 0) + '%';
    }
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  }

  function initAll() {
    initMenu();
    observeReveals();
    initProgress();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
  document.addEventListener('htmx:afterSettle', initAll);
})();
