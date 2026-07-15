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
      if (e.target.closest('a')) {
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // Stagger is assigned per IO callback batch (elements entering the viewport
  // together), and the inline delay is cleared after the reveal so it never
  // delays the element's own hover transitions.
  var observer = hasIO
    ? new IntersectionObserver(function (entries) {
        var visible = entries.filter(function (e) { return e.isIntersecting; });
        visible.forEach(function (entry, i) {
          var el = entry.target;
          el.style.transitionDelay = Math.min(i, 6) * 60 + 'ms';
          el.classList.add('is-visible');
          el.addEventListener('transitionend', function () {
            el.style.transitionDelay = '';
          }, { once: true });
          observer.unobserve(el);
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 })
    : null;

  function observeReveals() {
    if (!observer) return;
    var els = document.querySelectorAll('[data-reveal]:not(.is-observed)');
    els.forEach(function (el) {
      el.classList.add('is-observed');
      observer.observe(el);
    });
  }

  // JS fallback for browsers without CSS scroll-driven animations.
  // Listeners are bound once at module scope; the bar is re-resolved per page
  // (hx-boost replaces the whole body, so element references go stale).
  var progressBar = null;
  var needsProgressFallback = !(window.CSS && CSS.supports('animation-timeline: scroll()'));

  function updateProgress() {
    if (!progressBar) return;
    var doc = document.documentElement;
    var max = doc.scrollHeight - window.innerHeight;
    progressBar.style.width = (max > 0 ? Math.min(1, window.scrollY / max) * 100 : 0) + '%';
  }

  if (needsProgressFallback) {
    window.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress);
  }

  function initProgress() {
    if (!needsProgressFallback) return;
    progressBar = document.getElementById('progress');
    updateProgress();
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

  // Body swaps (hx-boost) replace observed elements; drop stale IO targets so
  // detached subtrees can be collected. New content re-observes after settle.
  document.addEventListener('htmx:beforeSwap', function (e) {
    if (observer && e.target === document.body) observer.disconnect();
  });
  // Comment reply forms (event delegation; comment partials arrive via htmx
  // swaps, so listeners live here — bound once — instead of inline scripts).
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.classList) return;
    if (t.classList.contains('reply-btn')) {
      var container = document.getElementById('reply-form-' + t.dataset.commentId);
      if (container) {
        container.classList.toggle('hidden');
        if (!container.classList.contains('hidden')) {
          var textarea = container.querySelector('textarea');
          if (textarea) textarea.focus();
        }
      }
    }
    if (t.classList.contains('cancel-reply')) {
      var wrap = t.closest('.reply-form-container');
      if (wrap) {
        wrap.classList.add('hidden');
        var form = wrap.querySelector('form');
        if (form) form.reset();
      }
    }
  });
  document.addEventListener('htmx:afterRequest', function (e) {
    if (e.detail.successful && e.target.classList && e.target.classList.contains('reply-form')) {
      var wrap = e.target.closest('.reply-form-container');
      if (wrap) {
        wrap.classList.add('hidden');
        e.target.reset();
      }
    }
  });
})();
