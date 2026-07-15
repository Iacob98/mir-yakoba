# Light Editorial Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle all public pages of the blog into the approved light editorial design (spec: `docs/superpowers/specs/2026-07-14-light-editorial-redesign-design.md`), replacing Tailwind CDN with a hand-written CSS design system plus a restrained micro-animation layer.

**Architecture:** One stylesheet (`static/css/site.css`, design tokens + semantic component classes) and one small script (`static/js/site.js`) serve every public template. Admin pages are decoupled first onto `admin_base.html` (a frozen copy of the current Tailwind base) so they keep working untouched. Backend changes are limited to: one context addition in the `home` route and two presentation-only HTML fragments in the auth API.

**Tech Stack:** Jinja2 templates, htmx 1.9 (kept as-is), vanilla CSS/JS. No build step, no new dependencies.

---

## Prerequisites

- Dev stack running: `docker compose up -d` (app on http://localhost:8000). Templates and `static/` are volume-mounted; Jinja auto-reloads templates on refresh, no restart needed.
- Every commit message ends with the trailer line: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (shown in commit steps as `<trailer>` to keep the plan short — substitute the real line).
- Verification uses `curl` against the running stack. If a page needs data (posts/images) and the local DB is empty, structural greps on the template files are the fallback — each task lists both.

## File Map

| File | Action | Responsibility |
|---|---|---|
| `static/css/site.css` | create | entire design system: tokens, components, animations |
| `static/js/site.js` | create | mobile menu, scroll-reveal observer, reading-progress fallback |
| `templates/admin_base.html` | create (copy) | frozen Tailwind base for admin pages only |
| `templates/admin/{dashboard,post_edit,settings,user_edit,users}.html` | modify (1 line each) | point at `admin_base.html` |
| `templates/base.html` | rewrite | public chrome: fonts, nav, footer, htmx config |
| `templates/pages/home.html` | rewrite | hero, feed container, gallery strip, author block |
| `templates/partials/posts_list.html` | rewrite | pinned card (page 1) + journal log rows |
| `src/web/router.py` (home route only) | modify | add `recent_images` to home context |
| `templates/pages/post_detail.html` | rewrite | article layout, progress thread, media, comments shell |
| `templates/partials/comments_list.html`, `templates/partials/comment.html` | rewrite | comment cards in-system (htmx attrs unchanged) |
| `templates/pages/gallery.html` | rewrite | masonry of image tiles |
| `templates/pages/works.html` | rewrite | masonry of work tiles with captions |
| `templates/pages/search.html`, `templates/partials/search_results.html` | rewrite | search form + result rows |
| `templates/pages/login.html` | rewrite | steps + code input |
| `src/api/v1/auth.py` (2 HTML fragments) | modify | error/success notices in system classes |
| `templates/pages/profile.html` | rewrite | profile, XP bar, achievements |
| `templates/partials/gallery_grid.html` | delete | orphaned (no route renders it) |
| `templates/partials/media_item.html` | keep as-is | admin-only (rendered inside `admin/post_edit.html`) |

---

### Task 1: Design system stylesheet

**Files:**
- Create: `static/css/site.css`

- [ ] **Step 1: Write `static/css/site.css`**

```css
/* Мир Якоба — light editorial design system.
   Single stylesheet for all public pages. Admin pages use admin_base.html. */

/* ─── tokens ──────────────────────────────────────────────────────── */
:root {
  --bg:      #fbf8f1;
  --surface: #ffffff;
  --fg:      #211d16;
  --muted:   #5b5344;
  --faint:   #a89e8c;
  --border:  rgba(33, 29, 22, 0.13);
  --accent:  #a16207;
  --accent-strong: #8a5306;
  --accent-soft: rgba(161, 98, 7, 0.13);
  --fg-soft: rgba(33, 29, 22, 0.055);
  --ok:      #3f6212;
  --err:     #a13c1a;
  --shadow-card: 0 1px 2px rgba(33, 29, 22, 0.05), 0 10px 28px rgba(33, 29, 22, 0.07);

  --font-display: 'Literata', Georgia, 'Times New Roman', serif;
  --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --font-mono: ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, monospace;

  --fs-h1: clamp(30px, 5.4vw, 54px);
  --fs-h2: clamp(22px, 3.4vw, 32px);
  --fs-h3: 19px;
  --fs-lead: 18px;
  --fs-body: 16px;
  --fs-meta: 13px;

  --gap-sm: 12px;
  --gap-md: 20px;
  --gap-lg: 32px;
  --gap-xl: 56px;
  --gap-2xl: 88px;
  --container: 1080px;
  --article: 700px;
  --gutter: 24px;

  --radius: 10px;
  --radius-lg: 16px;
}

/* ─── reset & base ─────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: 1.65;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
img, svg, video, canvas { display: block; max-width: 100%; }
a { color: inherit; text-decoration: none; }
button { font: inherit; cursor: pointer; }
p { text-wrap: pretty; }
h1, h2, h3 { text-wrap: balance; }

/* ─── a11y ─────────────────────────────────────────────────────────── */
.skip-link {
  position: absolute; left: -9999px; top: 0; z-index: 50;
  background: var(--fg); color: var(--bg);
  padding: 12px 20px; font-size: 14px; font-weight: 600;
  border-radius: 0 0 var(--radius) 0;
}
.skip-link:focus-visible { left: 0; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
::selection { background: var(--accent-soft); }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}

/* ─── utilities ────────────────────────────────────────────────────── */
.hidden { display: none !important; }
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.linklike { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--faint); }
.linklike:hover { text-decoration-color: var(--fg); }

/* ─── layout ───────────────────────────────────────────────────────── */
.container { max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
.article-col { max-width: var(--article); margin-inline: auto; padding-inline: var(--gutter); }
.narrow-col { max-width: 440px; margin-inline: auto; padding-inline: var(--gutter); }
.section { padding-block: clamp(40px, 6.5vw, var(--gap-2xl)); }
.section + .section { border-top: 1px solid var(--border); }
.section-head { margin-bottom: var(--gap-md); }
.row { display: flex; align-items: center; gap: var(--gap-md); }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: var(--gap-md); }
.grid-1-2 { display: grid; grid-template-columns: 1fr 2fr; gap: var(--gap-xl); align-items: center; }
@media (max-width: 920px) { .grid-1-2 { grid-template-columns: 1fr; gap: var(--gap-lg); } }

/* ─── type ─────────────────────────────────────────────────────────── */
h1 { font-family: var(--font-display); font-size: var(--fs-h1); line-height: 1.12; letter-spacing: -0.01em; margin: 0; font-weight: 700; }
h2 { font-family: var(--font-display); font-size: var(--fs-h2); line-height: 1.18; margin: 0; font-weight: 700; }
h3 { font-size: var(--fs-h3); font-weight: 650; line-height: 1.35; margin: 0; }
.lead { font-size: var(--fs-lead); line-height: 1.6; color: var(--muted); max-width: 58ch; margin: 0; }
.dek { color: var(--muted); }
.kicker {
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); margin: 0 0 var(--gap-md);
}
.kicker-accent { color: var(--accent); }
.meta { font-family: var(--font-mono); font-size: var(--fs-meta); color: var(--faint); }
.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

/* ─── chrome: nav + footer ─────────────────────────────────────────── */
.topnav {
  position: sticky; top: 0; z-index: 30;
  background: rgba(251, 248, 241, 0.86);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
}
.topnav-inner { display: flex; align-items: center; justify-content: space-between; padding-block: 14px; gap: var(--gap-md); }
.topnav .logo { font-family: var(--font-display); font-size: 19px; font-weight: 700; }
.topnav nav { display: flex; gap: var(--gap-lg); align-items: center; }
.topnav nav a { font-size: 14px; color: var(--muted); padding-block: 10px; transition: color 0.15s ease; }
.topnav nav a:hover, .topnav nav a[aria-current="page"] { color: var(--fg); }
.topnav form { display: inline; }
.topnav .logout-btn { background: none; border: 0; padding: 10px 0; font-size: 14px; color: var(--faint); }
.topnav .logout-btn:hover { color: var(--fg); }
.nav-toggle {
  display: none; background: none; border: 1px solid var(--border);
  border-radius: var(--radius); padding: 8px 12px; color: var(--fg);
  min-height: 44px; align-items: center; gap: 8px;
}
.mobile-nav { display: none; border-top: 1px solid var(--border); padding-block: var(--gap-sm) var(--gap-md); }
.mobile-nav a, .mobile-nav .logout-btn {
  display: block; width: 100%; text-align: left; padding: 12px 0;
  font-size: 16px; color: var(--fg); border: 0; border-bottom: 1px solid var(--border);
  background: none; min-height: 44px;
}
.mobile-nav.open { display: block; }
@media (max-width: 920px) {
  .topnav nav.desktop { display: none; }
  .nav-toggle { display: inline-flex; }
}
.pagefoot { padding-block: var(--gap-xl); color: var(--muted); font-size: 13px; border-top: 1px solid var(--border); margin-top: var(--gap-2xl); }
.pagefoot .row-between { flex-wrap: wrap; gap: var(--gap-md); align-items: flex-start; }
.pagefoot .foot-logo { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--fg); }
.pagefoot a { display: inline-block; padding-block: 6px; }
.pagefoot a:hover { color: var(--fg); }

/* ─── buttons & tags ───────────────────────────────────────────────── */
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 22px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 15px; font-weight: 600; min-height: 44px;
  transition: transform 0.05s ease, background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.btn:active { transform: translateY(1px); }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: transparent; color: var(--fg); border-color: var(--border); }
.btn-secondary:hover { border-color: var(--fg); }
.btn-ghost { background: transparent; color: var(--fg); border-color: transparent; padding-inline: 8px; }
.btn-ghost:hover { color: var(--accent); }
.btn-arrow::after { content: '→'; transition: transform 0.15s ease; }
.btn-arrow:hover::after { transform: translateX(3px); }
.btn-block { width: 100%; justify-content: center; }
.btn-sm { min-height: 40px; padding: 8px 16px; }
.tag {
  display: inline-flex; align-items: center;
  padding: 4px 11px;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
  white-space: nowrap;
}
.tag-accent { color: var(--accent); border-color: var(--accent-soft); background: var(--accent-soft); }

/* ─── hero ─────────────────────────────────────────────────────────── */
.hero { position: relative; padding-block: clamp(56px, 9vw, 120px) clamp(40px, 6vw, 72px); overflow: hidden; }
.hero::before {
  content: "";
  position: absolute; inset: -40% -20% auto -20%; height: 130%;
  background: radial-gradient(ellipse 55% 60% at 50% 0%, var(--accent-soft), transparent 70%);
  pointer-events: none;
}
.hero-inner { position: relative; max-width: 640px; }
.hero .lead { margin-top: 18px; }
.hero-avatar { width: 64px; height: 64px; border-radius: 999px; object-fit: cover; border: 1px solid var(--border); margin-bottom: 22px; }
.hero-actions { margin-top: 26px; flex-wrap: wrap; }

/* ─── pinned card ──────────────────────────────────────────────────── */
.pinned {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: clamp(22px, 4vw, 36px);
  margin-bottom: var(--gap-lg);
}
.pinned h2 a:hover { color: var(--accent); }
.pinned .dek { margin: 12px 0 0; max-width: 60ch; }
.pinned-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--gap-sm); margin-top: 20px; }

/* ─── journal feed ─────────────────────────────────────────────────── */
.log-row {
  display: grid; grid-template-columns: 112px 1fr 150px;
  gap: var(--gap-lg); padding: 24px 0;
  border-bottom: 1px solid var(--border);
  align-items: baseline;
}
.log-row h3 { font-size: 18px; }
.log-row h3 a { transition: color 0.15s ease; }
.log-row h3 a:hover { color: var(--accent); }
.log-row .dek { margin: 6px 0 0; font-size: 14px; max-width: 62ch; }
.log-row .pull { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
@media (max-width: 920px) {
  .log-row { grid-template-columns: 1fr; gap: 8px; padding: 20px 0; }
  .log-row .pull { flex-direction: row; align-items: center; text-align: left; order: -1; justify-content: space-between; width: 100%; }
}
.thumb-strip { display: flex; gap: 8px; margin-top: 12px; }
.thumb-strip img {
  width: 64px; height: 64px; object-fit: cover;
  border-radius: var(--radius); border: 1px solid var(--border);
  transition: transform 0.4s ease;
}
.log-row:hover .thumb-strip img { transform: scale(1.04); }
.doc-chip {
  display: inline-flex; align-items: center; gap: 8px;
  margin-top: 12px; padding: 8px 12px;
  border: 1px solid var(--border); background: var(--surface);
  border-radius: var(--radius);
  font-family: var(--font-mono); font-size: 12px; color: var(--muted);
}
.doc-chip svg { width: 14px; height: 14px; flex: none; }
.feed-sentinel { display: flex; justify-content: center; padding-block: 40px; }
.spinner {
  width: 24px; height: 24px; border-radius: 999px;
  border: 2px solid var(--border); border-top-color: var(--fg);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(1turn); } }
.empty-state { text-align: center; padding-block: 64px; color: var(--faint); }

/* ─── gallery strip & masonry tiles ────────────────────────────────── */
.gallery-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--gap-sm); }
@media (max-width: 920px) { .gallery-strip { grid-template-columns: repeat(2, 1fr); } }
.gallery-strip a {
  display: block; border-radius: var(--radius-lg); overflow: hidden;
  border: 1px solid var(--border); transition: border-color 0.2s ease;
}
.gallery-strip a:hover { border-color: var(--accent); }
.gallery-strip img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; transition: transform 0.5s ease; }
.gallery-strip a:hover img { transform: scale(1.03); }
.masonry { columns: 2; column-gap: var(--gap-sm); }
@media (min-width: 768px) { .masonry { columns: 3; } }
.masonry > * { break-inside: avoid; margin-bottom: var(--gap-sm); }
.tile {
  display: block; border-radius: var(--radius-lg); overflow: hidden;
  background: var(--surface); border: 1px solid var(--border);
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.tile:hover { box-shadow: var(--shadow-card); border-color: var(--accent); }
.tile img { width: 100%; transition: transform 0.5s ease; }
.tile:hover img { transform: scale(1.03); }
.tile-ph {
  aspect-ratio: 1 / 1; display: grid; place-items: center;
  background: var(--fg-soft);
  font-family: var(--font-display); font-size: 44px; color: var(--faint);
}
.tile-caption { padding: 12px 14px; }
.tile-caption h3 { font-size: 15px; line-height: 1.35; }
.tile-caption .meta { margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap; }

/* ─── author block ─────────────────────────────────────────────────── */
.author-photo { width: 100%; max-width: 260px; aspect-ratio: 1/1; object-fit: cover; border-radius: var(--radius-lg); border: 1px solid var(--border); }
@media (max-width: 920px) { .author-photo { max-width: 180px; } }

/* ─── article ──────────────────────────────────────────────────────── */
.progress { position: fixed; top: 0; left: 0; height: 3px; width: 0; background: var(--accent); z-index: 40; }
@supports (animation-timeline: scroll()) {
  .progress {
    width: 100%; transform: scaleX(0); transform-origin: 0 50%;
    animation: progress-grow auto linear;
    animation-timeline: scroll(root);
  }
  @keyframes progress-grow { to { transform: scaleX(1); } }
}
.article-head { padding-block: clamp(40px, 7vw, 80px) clamp(24px, 4vw, 44px); }
.article-head h1 { font-size: clamp(26px, 4.6vw, 44px); margin-bottom: var(--gap-md); }
.article-head .dek { font-size: var(--fs-lead); max-width: 56ch; margin: 0; line-height: 1.6; }
.byline { display: flex; align-items: center; gap: 14px; margin-top: var(--gap-lg); padding-top: var(--gap-md); border-top: 1px solid var(--border); }
.byline .who { font-size: 14px; font-weight: 650; }
.byline .when { font-family: var(--font-mono); font-size: 12px; color: var(--faint); margin-top: 2px; }
.ava {
  width: 40px; height: 40px; border-radius: 999px; flex: none;
  display: grid; place-items: center;
  background: var(--fg-soft); border: 1px solid var(--border);
  font-weight: 700; font-size: 15px;
}
.cover { margin: 0 0 clamp(24px, 4.5vw, 48px); }
.cover img { border-radius: var(--radius-lg); border: 1px solid var(--border); width: 100%; max-height: 520px; object-fit: cover; }
.cover figcaption { font-family: var(--font-mono); font-size: 12px; color: var(--faint); margin-top: 8px; }
.article-body { padding-bottom: clamp(36px, 5.5vw, 64px); font-size: 17px; line-height: 1.7; }

/* Editor.js / markdown content */
.prose p { margin: 0 0 1.35em; }
.prose h2 { font-family: var(--font-display); font-size: var(--fs-h2); line-height: 1.25; margin: 1.9em 0 0.7em; font-weight: 700; }
.prose h3 { font-family: var(--font-display); font-size: 20px; margin: 1.6em 0 0.6em; font-weight: 700; }
.prose ul, .prose ol { padding-left: 1.2em; margin: 0 0 1.35em; }
.prose li { margin-bottom: 0.4em; }
.prose blockquote {
  font-size: clamp(19px, 2.2vw, 23px); line-height: 1.5; font-weight: 550;
  margin: 1.6em 0; padding: 4px 0 4px 22px;
  border-left: 3px solid var(--accent);
}
.prose code {
  font-family: var(--font-mono); font-size: 0.85em;
  background: var(--fg-soft); padding: 2px 6px; border-radius: 6px;
}
.prose pre {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px 20px; overflow-x: auto; margin: 0 0 1.35em;
  font-family: var(--font-mono); font-size: 13.5px; line-height: 1.6;
}
.prose pre code { background: none; padding: 0; }
.prose a { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--faint); }
.prose a:hover { text-decoration-color: var(--fg); }
.prose img { border-radius: var(--radius-lg); }
.prose figure { margin: 2rem 0; }
.prose figcaption { text-align: center; color: var(--faint); margin-top: 0.5rem; font-family: var(--font-mono); font-size: 12px; }

/* post media attachments */
.media-list { display: grid; gap: var(--gap-md); margin-top: var(--gap-xl); }
.media-list figure { margin: 0; }
.media-list img, .media-list video { width: 100%; border-radius: var(--radius-lg); border: 1px solid var(--border); }
.media-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px; }
.media-block .meta { margin-bottom: 10px; display: block; }
.media-block audio { width: 100%; }
.pdf-viewer { border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border); background: var(--fg-soft); }
.pdf-pages { display: grid; gap: 8px; padding: 8px; }
.pdf-pages canvas { width: 100%; display: block; }
.pdf-error { color: var(--err); padding: 16px; }

/* ─── comments ─────────────────────────────────────────────────────── */
.comments { border-top: 1px solid var(--border); padding-block: var(--gap-xl); }
.comments h2 { margin-bottom: var(--gap-lg); }
.comment { display: grid; grid-template-columns: 40px 1fr; gap: 14px; padding: 20px 0; border-top: 1px solid var(--border); }
.comment .head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.comment .name { font-size: 14px; font-weight: 650; }
.comment p { margin: 6px 0 0; font-size: 15px; white-space: pre-wrap; }
.comment .actions { margin-top: 6px; display: flex; gap: 14px; }
.comment .actions button { background: none; border: 0; padding: 0; font-size: 12px; color: var(--faint); }
.comment .actions button:hover { color: var(--accent); }
.comment .actions .danger:hover { color: var(--err); }
.comment-replies { border-left: 1px solid var(--border); padding-left: 16px; margin-top: 4px; }
.comment-replies .comment { border-top: 0; padding: 12px 0; }
.reply-form-container form { margin-top: 10px; }

/* ─── forms ────────────────────────────────────────────────────────── */
.field {
  width: 100%; padding: 14px 16px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); color: var(--fg);
  font: inherit; line-height: 1.55;
}
.field:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
textarea.field { resize: vertical; min-height: 96px; }
.field-lg { padding: 16px 20px; font-size: 18px; }
.code-input {
  text-align: center; font-family: var(--font-mono);
  font-size: 24px; letter-spacing: 0.3em; text-transform: uppercase;
}
.form-label {
  display: block; font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--faint);
  margin-bottom: 8px;
}
.form-hint { font-family: var(--font-mono); font-size: 12px; color: var(--faint); }
.notice { padding: 14px 16px; border-radius: var(--radius); border: 1px solid var(--border); margin-bottom: 16px; font-size: 14px; }
.notice-error { color: var(--err); border-color: rgba(161, 60, 26, 0.4); background: rgba(161, 60, 26, 0.07); }
.notice-success { color: var(--ok); border-color: rgba(63, 98, 18, 0.4); background: rgba(63, 98, 18, 0.07); }

/* ─── login steps ──────────────────────────────────────────────────── */
.steps { display: grid; gap: var(--gap-md); margin-bottom: var(--gap-lg); }
.step { display: flex; gap: 14px; align-items: flex-start; }
.step .n {
  flex: none; width: 28px; height: 28px; border-radius: 999px;
  display: grid; place-items: center;
  background: var(--fg); color: var(--bg);
  font-family: var(--font-mono); font-size: 12px;
}
.step p { margin: 2px 0 0; font-size: 14px; color: var(--muted); }

/* ─── profile ──────────────────────────────────────────────────────── */
.profile-head { text-align: center; margin-bottom: var(--gap-lg); }
.profile-head .ava { width: 72px; height: 72px; font-size: 26px; margin-inline: auto; margin-bottom: 14px; }
.stat-row { display: flex; justify-content: space-between; align-items: baseline; padding-block: 8px; font-size: 14px; }
.stat-row .k { color: var(--faint); }
.xp-bar { height: 8px; background: var(--fg-soft); border-radius: 999px; overflow: hidden; }
.xp-bar > div { height: 100%; background: var(--accent); border-radius: 999px; transition: width 0.4s ease; }
.ach-row { display: flex; gap: 12px; align-items: flex-start; padding-block: 10px; }
.ach-row img, .ach-row .ach-ph { width: 48px; height: 48px; border-radius: var(--radius); object-fit: cover; flex: none; }
.ach-row .ach-ph { display: grid; place-items: center; background: var(--fg-soft); font-weight: 700; color: var(--faint); }
.ach-row h4 { margin: 0; font-size: 14px; }
.ach-row p { margin: 2px 0 0; font-size: 12px; color: var(--faint); }
.divider { border: 0; border-top: 1px solid var(--border); margin-block: var(--gap-lg); }

/* ─── animations: scroll reveal + view transitions ─────────────────── */
/* Hidden state only when JS confirmed IntersectionObserver support
   (html.has-reveal set by site.js), so content is never lost without JS. */
.has-reveal [data-reveal] {
  opacity: 0; transform: translateY(16px);
  transition: opacity 0.55s ease, transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}
.has-reveal [data-reveal].is-visible { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) {
  .has-reveal [data-reveal] { opacity: 1; transform: none; transition: none; }
}
@media (prefers-reduced-motion: no-preference) {
  ::view-transition-old(root), ::view-transition-new(root) { animation-duration: 180ms; }
}
```

- [ ] **Step 2: Verify the file is served**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/static/css/site.css`
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add static/css/site.css
git commit -m "feat(redesign): add light editorial design system stylesheet" -m "<trailer>"
```

---

### Task 2: Site script (menu, reveal, progress)

**Files:**
- Create: `static/js/site.js`

- [ ] **Step 1: Write `static/js/site.js`**

```js
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
```

- [ ] **Step 2: Verify the file is served**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/static/js/site.js`
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add static/js/site.js
git commit -m "feat(redesign): add site.js (menu, scroll reveal, reading progress)" -m "<trailer>"
```

---

### Task 3: Decouple admin pages from the public base

Admin templates currently extend `base.html` and rely on Tailwind utilities. Freeze the current base as `admin_base.html` BEFORE rewriting `base.html`.

**Files:**
- Create: `templates/admin_base.html` (copy of current `templates/base.html`)
- Modify: `templates/admin/dashboard.html:1`, `templates/admin/post_edit.html:1`, `templates/admin/settings.html:1`, `templates/admin/user_edit.html:1`, `templates/admin/users.html:1`

- [ ] **Step 1: Copy the current base**

```bash
cp templates/base.html templates/admin_base.html
```

- [ ] **Step 2: Repoint the five admin templates**

```bash
sed -i 's|{% extends "base.html" %}|{% extends "admin_base.html" %}|' \
  templates/admin/dashboard.html templates/admin/post_edit.html \
  templates/admin/settings.html templates/admin/user_edit.html templates/admin/users.html
```

- [ ] **Step 3: Verify**

Run: `grep -l 'extends "admin_base.html"' templates/admin/*.html | wc -l`
Expected: `5`

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/admin`
Expected: `302` (redirect to login when unauthenticated) — confirms the route still renders without template errors.

- [ ] **Step 4: Commit**

```bash
git add templates/admin_base.html templates/admin/
git commit -m "refactor(redesign): freeze Tailwind base as admin_base.html for admin pages" -m "<trailer>"
```

---

### Task 4: Rewrite the public base template

**Files:**
- Rewrite: `templates/base.html`

- [ ] **Step 1: Replace `templates/base.html` entirely**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ title }}{% endblock %} | Мир Якоба</title>
    <link rel="icon" type="image/png" href="/static/favicon.png">
    <link rel="apple-touch-icon" href="/static/favicon.png">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,700;1,7..72,700&display=swap" rel="stylesheet">

    <link rel="stylesheet" href="/static/css/site.css">

    <meta name="htmx-config" content='{"globalViewTransitions": true}'>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="/static/js/site.js" defer></script>

    {% block head %}{% endblock %}
</head>
<body hx-boost="true">
    <a class="skip-link" href="#content">Перейти к содержанию</a>

    <header class="topnav">
        <div class="container">
            <div class="topnav-inner">
                <a href="/" class="logo">Мир Якоба</a>
                <nav class="desktop">
                    <a href="/">Главная</a>
                    <a href="/gallery">Галерея</a>
                    <a href="/works">Мои работы</a>
                    <a href="/search">Поиск</a>
                    {% if user %}
                        {% if user.is_admin %}<a href="/admin">Админ</a>{% endif %}
                        <a href="/profile">{{ user.display_name }}</a>
                        <form action="/api/v1/auth/logout" method="POST" hx-boost="false">
                            <button type="submit" class="logout-btn">Выйти</button>
                        </form>
                    {% else %}
                        <a href="/login" class="btn btn-secondary btn-sm">Войти</a>
                    {% endif %}
                </nav>
                <button class="nav-toggle" id="navToggle" aria-expanded="false" aria-controls="mobileNav">
                    Меню
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
                </button>
            </div>
            <div class="mobile-nav" id="mobileNav">
                <a href="/">Главная</a>
                <a href="/gallery">Галерея</a>
                <a href="/works">Мои работы</a>
                <a href="/search">Поиск</a>
                {% if user %}
                    {% if user.is_admin %}<a href="/admin">Админ</a>{% endif %}
                    <a href="/profile">{{ user.display_name }}</a>
                    <form action="/api/v1/auth/logout" method="POST" hx-boost="false">
                        <button type="submit" class="logout-btn">Выйти</button>
                    </form>
                {% else %}
                    <a href="/login" style="font-weight: 600; border-bottom: 0;">Войти</a>
                {% endif %}
            </div>
        </div>
    </header>

    <main id="content">
        {% block content %}{% endblock %}
    </main>

    <footer class="pagefoot">
        <div class="container">
            <div class="row-between">
                <div>
                    <a href="/" class="foot-logo">Мир Якоба</a>
                    <p style="margin: 6px 0 0;">Творчество, мысли и код</p>
                </div>
                <nav class="row" style="gap: 24px; flex-wrap: wrap;">
                    <a href="/">Главная</a>
                    <a href="/gallery">Галерея</a>
                    <a href="/works">Мои работы</a>
                    <a href="/search">Поиск</a>
                </nav>
            </div>
            <p class="meta" style="margin-top: 32px;">© 2026 Мир Якоба · вход по коду из Telegram, без паролей</p>
        </div>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Verify**

Run: `curl -s http://localhost:8000/ | grep -c 'site.css'` → Expected: `1`
Run: `curl -s http://localhost:8000/ | grep -c 'cdn.tailwindcss.com'` → Expected: `0`
Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/` → Expected: `200`

(Home page body will look broken until Task 5 — only the chrome is in-system at this point. That's expected.)

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat(redesign): light editorial base template, drop Tailwind CDN from public pages" -m "<trailer>"
```

---

### Task 5: Home page (journal composition)

**Files:**
- Modify: `src/web/router.py:49-60` (home route)
- Rewrite: `templates/pages/home.html`
- Rewrite: `templates/partials/posts_list.html`

- [ ] **Step 1: Add `recent_images` to the home route in `src/web/router.py`**

Replace the existing `home` function (lines 49–60) with:

```python
@web_router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from src.services.media import MediaService

    if user and user.is_admin:
        access_level = AccessLevel.PREMIUM_2
    else:
        access_level = user.access_level if user else AccessLevel.PUBLIC

    settings_service = SettingsService(db)
    hero = await settings_service.get_hero_settings()
    media_service = MediaService(db)
    recent_images = await media_service.list_all_images(
        user_access_level=access_level,
        limit=4,
    )
    return templates.TemplateResponse(
        "pages/home.html",
        {
            "request": request,
            "title": "Главная",
            "user": user,
            "hero": hero,
            "recent_images": recent_images,
        },
    )
```

- [ ] **Step 2: Replace `templates/pages/home.html` entirely**

```html
{% extends "base.html" %}

{% block title %}Главная{% endblock %}

{% block content %}
<!-- Hero -->
<section class="hero">
    <div class="container hero-inner">
        {% if hero.avatar %}
        <img class="hero-avatar" src="/static/{{ hero.avatar }}" alt="Якоб — автор блога" data-reveal>
        {% endif %}
        <h1 data-reveal>{{ hero.title }}</h1>
        <p class="lead" data-reveal>{{ hero.subtitle }}</p>
    </div>
</section>

<!-- Journal feed (pinned card + log rows come from the partial) -->
<section class="section" id="posts" style="padding-top: 0; border-top: 0;">
    <div class="container">
        <div class="row-between section-head" data-reveal>
            <h2>Свежие записи</h2>
        </div>
        <div id="posts-container"
             hx-get="/partials/posts"
             hx-trigger="load"
             hx-swap="innerHTML">
            <div class="feed-sentinel"><div class="spinner"></div></div>
        </div>
    </div>
</section>

<!-- Gallery strip -->
{% if recent_images %}
<section class="section" id="gallery">
    <div class="container">
        <div class="row-between section-head" data-reveal>
            <h2>Последние работы</h2>
            <a class="btn btn-ghost btn-arrow" href="/gallery">Открыть галерею</a>
        </div>
        <div class="gallery-strip">
            {% for img in recent_images %}
            <a href="{% if img.post %}/posts/{{ img.post.slug }}{% else %}/gallery{% endif %}" data-reveal>
                <img src="/uploads/{{ img.file_path }}" alt="{{ img.original_name }}" loading="lazy">
            </a>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

<!-- Author + login CTA (guests only) -->
{% if not user %}
<section class="section" id="author">
    <div class="container grid-1-2">
        {% if hero.avatar %}
        <img class="author-photo" src="/static/{{ hero.avatar }}" alt="Якоб — автор блога" data-reveal>
        {% endif %}
        <div data-reveal>
            <p class="kicker">Об авторе</p>
            <h2 style="max-width: 24ch;">Читайте со своего уровня</h2>
            <p class="lead" style="margin-top: 14px;">За комментарии и чтение начисляется опыт, бот присылает карточки достижений, а команда /level показывает, сколько осталось до следующего уровня. Вход занимает полминуты.</p>
            <div class="row hero-actions">
                <a class="btn btn-primary" href="/login">Войти через Telegram</a>
                <a class="btn btn-ghost btn-arrow" href="/works">Мои работы</a>
            </div>
        </div>
    </div>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Replace `templates/partials/posts_list.html` entirely**

Notes: `list_posts()` sorts pinned posts first, so on page 1 a pinned post (if any) is always `posts[0]`. Rows use `border-bottom`, so appended pages (infinite scroll returns this same partial) join seamlessly.

```html
{% if posts %}

{% if page == 1 and posts[0].is_pinned %}
{% set pinned = posts[0] %}
{% set feed = posts[1:] %}
<article class="pinned" data-reveal>
    <p class="kicker kicker-accent" style="margin-bottom: 12px;">Закреплено</p>
    <h2><a href="/posts/{{ pinned.slug }}">{{ pinned.title }}</a></h2>
    {% if pinned.excerpt %}<p class="dek">{{ pinned.excerpt }}</p>{% endif %}
    <div class="pinned-meta">
        {% if pinned.published_at %}
        <span class="meta num">{{ pinned.published_at.strftime('%d.%m.%Y') }}</span>
        <span class="meta">·</span>
        {% endif %}
        <span class="meta num">{{ pinned.view_count }} просмотров</span>
        <a class="btn btn-ghost btn-arrow" href="/posts/{{ pinned.slug }}">Читать</a>
    </div>
</article>
{% else %}
{% set feed = posts %}
{% endif %}

{% for post in feed %}
{% set images = post.media | selectattr('media_type.value', 'equalto', 'image') | list %}
{% set docs = post.media | selectattr('media_type.value', 'equalto', 'document') | list %}
<article class="log-row" data-reveal>
    <span class="meta num">{% if post.published_at %}{{ post.published_at.strftime('%d.%m.%Y') }}{% else %}Черновик{% endif %}</span>
    <div>
        <h3><a href="/posts/{{ post.slug }}">{{ post.title }}</a></h3>
        {% if post.excerpt %}<p class="dek">{{ post.excerpt }}</p>{% endif %}
        {% if images %}
        <div class="thumb-strip">
            {% for img in images[:3] %}
            <img src="/uploads/{{ img.file_path }}" alt="{{ img.original_name }}" loading="lazy">
            {% endfor %}
        </div>
        {% elif docs %}
        <span class="doc-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z"/><path d="M14 3v4h4"/></svg>
            PDF · {{ docs | length }} шт.
        </span>
        {% endif %}
    </div>
    <span class="pull">
        {% if post.visibility.value != 'public' %}
        <span class="tag tag-accent">Для своих</span>
        {% elif post.post_type.value == 'photo' %}
        <span class="tag">Фото</span>
        {% elif post.post_type.value == 'work' %}
        <span class="tag">Работа</span>
        {% else %}
        <span class="tag">Заметка</span>
        {% endif %}
        <span class="meta num">{{ post.view_count }} просмотров</span>
    </span>
</article>
{% endfor %}

{% if has_more %}
<div hx-get="/partials/posts?page={{ next_page }}"
     hx-trigger="revealed"
     hx-swap="outerHTML"
     class="feed-sentinel">
    <div class="spinner"></div>
</div>
{% endif %}

{% else %}
<div class="empty-state">
    <p>Записей пока нет. Загляните позже!</p>
</div>
{% endif %}
```

- [ ] **Step 4: Verify**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/` → Expected: `200`
Run: `curl -s http://localhost:8000/ | grep -c 'class="hero'` → Expected: `1` or more
Run: `curl -s http://localhost:8000/partials/posts | head -c 400` → Expected: `.pinned` or `.log-row` markup (or the empty-state div if the DB has no posts) and NO Tailwind utility classes (`grid-cols`, `text-gray-…`).

- [ ] **Step 5: Commit**

```bash
git add src/web/router.py templates/pages/home.html templates/partials/posts_list.html
git commit -m "feat(redesign): journal home page — pinned card, log feed, gallery strip, author block" -m "<trailer>"
```

---

### Task 6: Post page + comments

**Files:**
- Rewrite: `templates/pages/post_detail.html`
- Rewrite: `templates/partials/comments_list.html`
- Rewrite: `templates/partials/comment.html`

All htmx attributes (`hx-post`, `hx-delete`, targets, `reply-btn`/`cancel-reply`/`reply-form-container` hooks and the delegation script) are preserved verbatim — only classes/markup change.

- [ ] **Step 1: Replace `templates/pages/post_detail.html` entirely**

```html
{% extends "base.html" %}

{% block title %}{% if post %}{{ post.title }}{% else %}Нет доступа{% endif %}{% endblock %}

{% block content %}
{% if access_denied %}
<div class="narrow-col" style="padding-block: 96px; text-align: center;">
    <p class="kicker kicker-accent">Доступ ограничен</p>
    <h1 style="font-size: var(--fs-h2); margin-bottom: 12px;">Недостаточный уровень доступа</h1>
    <p class="dek" style="margin-bottom: 24px;">Этот пост доступен для пользователей с более высоким уровнем подписки.</p>
    <a href="/" class="btn btn-secondary">Вернуться на главную</a>
</div>
{% else %}
<div class="progress" id="progress" aria-hidden="true"></div>
<article>
    <header class="article-col article-head">
        <p class="kicker">
            {% if post.visibility.value != 'public' %}<span class="kicker-accent">Для своих · </span>{% endif %}
            {% if post.post_type.value == 'photo' %}Фото{% elif post.post_type.value == 'work' %}Работа{% else %}Заметка{% endif %}
        </p>
        <h1>{{ post.title }}</h1>
        {% if post.excerpt %}<p class="dek">{{ post.excerpt }}</p>{% endif %}
        <div class="byline">
            {% if post.author %}
            <div class="ava">{{ post.author.display_name[0] | upper }}</div>
            <div>
                <div class="who">{{ post.author.display_name }}</div>
                <div class="when num">{% if post.published_at %}{{ post.published_at.strftime('%d.%m.%Y') }} · {% endif %}{{ post.view_count }} просмотров</div>
            </div>
            {% endif %}
            {% if user and user.is_admin %}
            <a href="/admin/posts/{{ post.id }}/edit" class="btn btn-ghost" style="margin-left: auto;">Редактировать</a>
            {% endif %}
        </div>
    </header>

    {% if post.featured_image %}
    <div class="article-col">
        <figure class="cover">
            <img src="{{ post.featured_image }}" alt="{{ post.title }}">
        </figure>
    </div>
    {% endif %}

    <div class="article-col article-body">
        <div class="prose">
            {{ post.content_html | safe }}
        </div>

        {% if post.media %}
        <div class="media-list">
            {% for media in post.media %}
                {% if media.media_type.value == 'image' %}
                <figure>
                    <img src="/uploads/{{ media.file_path }}" alt="{{ media.original_name }}" loading="lazy">
                </figure>
                {% elif media.media_type.value == 'audio' %}
                <div class="media-block">
                    <span class="meta">{{ media.original_name }}</span>
                    <audio controls>
                        <source src="/uploads/{{ media.file_path }}" type="{{ media.mime_type }}">
                    </audio>
                </div>
                {% elif media.media_type.value == 'video' %}
                <figure>
                    <video controls>
                        <source src="/uploads/{{ media.file_path }}" type="{{ media.mime_type }}">
                    </video>
                </figure>
                {% elif media.media_type.value == 'document' %}
                <div class="pdf-viewer" data-pdf-url="/uploads/{{ media.file_path }}">
                    <div class="pdf-pages"></div>
                </div>
                {% endif %}
            {% endfor %}
        </div>
        {% endif %}

        {% set has_pdf = post.media | selectattr('media_type.value', 'equalto', 'document') | list %}
        {% if has_pdf %}
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
        <script>
        (function() {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

            document.querySelectorAll('.pdf-viewer').forEach(function(viewer) {
                var url = viewer.dataset.pdfUrl;
                var container = viewer.querySelector('.pdf-pages');
                var containerWidth = viewer.clientWidth - 16;

                pdfjsLib.getDocument(url).promise.then(function(pdf) {
                    for (var i = 1; i <= pdf.numPages; i++) {
                        (function(pageNum) {
                            pdf.getPage(pageNum).then(function(page) {
                                var scale = containerWidth / page.getViewport({ scale: 1 }).width;
                                var viewport = page.getViewport({ scale: scale });
                                var canvas = document.createElement('canvas');
                                canvas.width = viewport.width;
                                canvas.height = viewport.height;
                                container.appendChild(canvas);
                                page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport });
                            });
                        })(i);
                    }
                }).catch(function(err) {
                    var errMsg = document.createElement('p');
                    errMsg.className = 'pdf-error';
                    errMsg.textContent = 'Ошибка загрузки PDF';
                    container.appendChild(errMsg);
                });
            });
        })();
        </script>
        {% endif %}
    </div>

    <section class="article-col comments">
        <h2>Комментарии</h2>

        {% if user %}
        <form hx-post="/api/v1/comments/{{ post.id }}"
              hx-target="#comments-list"
              hx-swap="afterbegin"
              hx-on::after-request="this.reset()"
              hx-disabled-elt="button[type='submit']"
              style="margin-bottom: 32px;">
            <textarea name="content"
                      rows="3"
                      class="field"
                      placeholder="Написать комментарий…"
                      required></textarea>
            <div class="row-between" style="margin-top: 12px; flex-wrap: wrap;">
                <span class="form-hint">Вы вошли как {{ user.display_name }}</span>
                <button type="submit" class="btn btn-primary">Отправить</button>
            </div>
        </form>
        {% else %}
        <p class="dek" style="margin-bottom: 32px;">
            <a href="/login" class="linklike">Войдите</a>, чтобы оставить комментарий.
        </p>
        {% endif %}

        <div id="comments-list"
             hx-get="/api/v1/comments/{{ post.id }}"
             hx-trigger="load"
             hx-swap="innerHTML">
            <p class="meta">Загрузка комментариев…</p>
        </div>
    </section>
</article>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Replace `templates/partials/comments_list.html` entirely**

```html
{% macro render_comment(comment, post_id, user, depth=0) %}
<div class="comment" id="comment-{{ comment.id }}">
    <div class="ava">{{ comment.author.display_name[0] | upper }}</div>
    <div>
        <div class="head">
            <span class="name">{{ comment.author.display_name }}</span>
            {% if comment.author.level > 0 %}
            <span class="tag">Lv.{{ comment.author.level }}</span>
            {% endif %}
            <span class="meta">{{ comment.created_at.strftime('%d.%m.%Y в %H:%M') if depth == 0 else comment.created_at.strftime('%d.%m в %H:%M') }}</span>
        </div>
        <p>{{ comment.content }}</p>

        <div class="actions">
            {% if user %}
            <button type="button"
                    class="reply-btn"
                    data-comment-id="{{ comment.id }}"
                    data-post-id="{{ post_id }}">
                Ответить
            </button>
            {% endif %}
            {% if user and (user.id == comment.author_id or user.is_admin) %}
            <button type="button"
                    class="danger"
                    hx-delete="/api/v1/comments/{{ comment.id }}"
                    hx-target="#comment-{{ comment.id }}"
                    hx-swap="outerHTML"
                    hx-confirm="Удалить этот комментарий?">
                Удалить
            </button>
            {% endif %}
        </div>

        {% if user %}
        <div id="reply-form-{{ comment.id }}" class="reply-form-container hidden">
            <form hx-post="/api/v1/comments/{{ post_id }}"
                  hx-target="#replies-{{ comment.id }}"
                  hx-swap="beforeend"
                  hx-disabled-elt="button[type='submit']"
                  class="reply-form">
                <input type="hidden" name="parent_id" value="{{ comment.id }}">
                <textarea name="content"
                          rows="2"
                          class="field"
                          placeholder="Написать ответ…"
                          required></textarea>
                <div class="row" style="gap: 8px; margin-top: 8px;">
                    <button type="submit" class="btn btn-primary btn-sm">Ответить</button>
                    <button type="button" class="cancel-reply btn btn-ghost btn-sm">Отмена</button>
                </div>
            </form>
        </div>
        {% endif %}

        <div id="replies-{{ comment.id }}" class="{% if comment._replies is defined and comment._replies %}comment-replies{% endif %}">
            {% if comment._replies is defined and comment._replies %}
                {% for reply in comment._replies %}
                    {{ render_comment(reply, post_id, user, depth + 1) }}
                {% endfor %}
            {% endif %}
        </div>
    </div>
</div>
{% endmacro %}

{% if comments %}
<div>
    {% for comment in comments %}
        {{ render_comment(comment, post_id, user, 0) }}
    {% endfor %}
</div>

<script>
document.addEventListener('click', function(e) {
    // Handle reply button click
    if (e.target.classList.contains('reply-btn')) {
        const commentId = e.target.dataset.commentId;
        const container = document.getElementById('reply-form-' + commentId);
        if (container) {
            container.classList.toggle('hidden');
            if (!container.classList.contains('hidden')) {
                const textarea = container.querySelector('textarea');
                if (textarea) textarea.focus();
            }
        }
    }
    // Handle cancel button click
    if (e.target.classList.contains('cancel-reply')) {
        const container = e.target.closest('.reply-form-container');
        if (container) {
            container.classList.add('hidden');
            const form = container.querySelector('form');
            if (form) form.reset();
        }
    }
});

// Hide form and reset after successful submission
document.body.addEventListener('htmx:afterRequest', function(e) {
    if (e.detail.successful && e.target.classList.contains('reply-form')) {
        const container = e.target.closest('.reply-form-container');
        if (container) {
            container.classList.add('hidden');
            e.target.reset();
        }
    }
});
</script>
{% else %}
<p class="dek">Комментариев пока нет.</p>
{% endif %}
```

- [ ] **Step 3: Replace `templates/partials/comment.html` entirely**

This partial renders one freshly-posted comment (htmx `afterbegin` into `#comments-list`, or `beforeend` into a replies container).

```html
<div class="comment" id="comment-{{ comment.id }}">
    <div class="ava">{{ comment.author.display_name[0] | upper }}</div>
    <div>
        <div class="head">
            <span class="name">{{ comment.author.display_name }}</span>
            {% if comment.author.level > 0 %}
            <span class="tag">Lv.{{ comment.author.level }}</span>
            {% endif %}
            <span class="meta">{{ comment.created_at.strftime('%d.%m в %H:%M') if comment.parent_id else comment.created_at.strftime('%d.%m.%Y в %H:%M') }}</span>
        </div>
        <p>{{ comment.content }}</p>

        <div class="actions">
            {% if user %}
            <button type="button"
                    class="reply-btn"
                    data-comment-id="{{ comment.id }}"
                    data-post-id="{{ comment.post_id }}">
                Ответить
            </button>
            {% endif %}
            {% if user and (user.id == comment.author_id or user.is_admin) %}
            <button type="button"
                    class="danger"
                    hx-delete="/api/v1/comments/{{ comment.id }}"
                    hx-target="#comment-{{ comment.id }}"
                    hx-swap="outerHTML"
                    hx-confirm="Удалить этот комментарий?">
                Удалить
            </button>
            {% endif %}
        </div>

        {% if user %}
        <div id="reply-form-{{ comment.id }}" class="reply-form-container hidden">
            <form hx-post="/api/v1/comments/{{ comment.post_id }}"
                  hx-target="#replies-{{ comment.id }}"
                  hx-swap="beforeend"
                  hx-disabled-elt="button[type='submit']"
                  class="reply-form">
                <input type="hidden" name="parent_id" value="{{ comment.id }}">
                <textarea name="content"
                          rows="2"
                          class="field"
                          placeholder="Написать ответ…"
                          required></textarea>
                <div class="row" style="gap: 8px; margin-top: 8px;">
                    <button type="submit" class="btn btn-primary btn-sm">Ответить</button>
                    <button type="button" class="cancel-reply btn btn-ghost btn-sm">Отмена</button>
                </div>
            </form>
        </div>
        {% endif %}

        <div id="replies-{{ comment.id }}"></div>
    </div>
</div>
```

- [ ] **Step 4: Verify**

```bash
SLUG=$(curl -s http://localhost:8000/partials/posts | grep -o '/posts/[^"]*' | head -1)
[ -n "$SLUG" ] && curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000$SLUG"
```
Expected: `200` (if the DB has no posts, fall back to a structural check: `python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('templates')).get_template('pages/post_detail.html')"` — must not raise).

- [ ] **Step 5: Commit**

```bash
git add templates/pages/post_detail.html templates/partials/comments_list.html templates/partials/comment.html
git commit -m "feat(redesign): article page with reading progress + in-system comments" -m "<trailer>"
```

---

### Task 7: Gallery page

**Files:**
- Rewrite: `templates/pages/gallery.html`

- [ ] **Step 1: Replace `templates/pages/gallery.html` entirely**

```html
{% extends "base.html" %}

{% block title %}Галерея{% endblock %}

{% block content %}
<section class="section" style="border-top: 0;">
    <div class="container">
        <div class="section-head" data-reveal>
            <p class="kicker">Фотографии</p>
            <h1 style="font-size: var(--fs-h2);">Галерея</h1>
            <p class="dek" style="margin-top: 8px;">Все изображения из публикаций</p>
        </div>

        {% if images %}
        <div class="masonry">
            {% for img in images %}
            <a href="{% if img.post %}/posts/{{ img.post.slug }}{% else %}#{% endif %}" class="tile" data-reveal>
                <img src="/uploads/{{ img.file_path }}" alt="{{ img.original_name }}" loading="lazy">
            </a>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <p>Фотографий пока нет</p>
        </div>
        {% endif %}
    </div>
</section>
{% endblock %}
```

- [ ] **Step 2: Verify**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/gallery` → Expected: `200`
Run: `curl -s http://localhost:8000/gallery | grep -c 'text-gray'` → Expected: `0`

- [ ] **Step 3: Commit**

```bash
git add templates/pages/gallery.html
git commit -m "feat(redesign): gallery page" -m "<trailer>"
```

---

### Task 8: Works page

**Files:**
- Rewrite: `templates/pages/works.html`

- [ ] **Step 1: Replace `templates/pages/works.html` entirely**

(The random-emoji/gradient placeholders are replaced with a quiet initial-letter tile; media-type badges become `.tag` chips in a caption below the image — the hover overlay is dropped.)

```html
{% extends "base.html" %}

{% block title %}Мои работы{% endblock %}

{% block content %}
<section class="section" style="border-top: 0;">
    <div class="container">
        <div class="section-head" data-reveal>
            <p class="kicker">Портфолио</p>
            <h1 style="font-size: var(--fs-h2);">Мои работы</h1>
            <p class="dek" style="margin-top: 8px;">Фото, видео и документы из моего портфолио</p>
        </div>

        {% if posts %}
        <div class="masonry">
            {% for post in posts %}
            <a href="/posts/{{ post.slug }}" class="tile" data-reveal>
                {% if post.featured_image %}
                <img src="{{ post.featured_image }}" alt="{{ post.title }}" loading="lazy">
                {% else %}
                <div class="tile-ph">{{ post.title[0] | upper }}</div>
                {% endif %}
                <div class="tile-caption">
                    <h3>{{ post.title }}</h3>
                    <div class="meta">
                        {% if post.published_at %}<span class="num">{{ post.published_at.strftime('%d.%m.%Y') }}</span>{% endif %}
                        {% for m in post.media %}
                            {% if m.media_type.value == 'video' %}<span class="tag">Видео</span>
                            {% elif m.media_type.value == 'document' %}<span class="tag">PDF</span>{% endif %}
                        {% endfor %}
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <p>Работы скоро появятся</p>
        </div>
        {% endif %}
    </div>
</section>
{% endblock %}
```

- [ ] **Step 2: Verify**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/works` → Expected: `200`
Run: `curl -s http://localhost:8000/works | grep -c 'bg-gradient'` → Expected: `0`

- [ ] **Step 3: Commit**

```bash
git add templates/pages/works.html
git commit -m "feat(redesign): works page with tile captions" -m "<trailer>"
```

---

### Task 9: Search page + results partial

**Files:**
- Rewrite: `templates/pages/search.html`
- Rewrite: `templates/partials/search_results.html`

The results block appears twice by design (SSR full-page results in `search.html`, live results in the partial) — keep both in sync using the same markup.

- [ ] **Step 1: Replace `templates/partials/search_results.html` entirely**

```html
{% if query %}
    {% if posts %}
    <p class="meta" style="margin-bottom: 20px;">Найдено: {{ total }}</p>
    <div>
        {% for post in posts %}
        <article class="log-row">
            <span class="meta num">{% if post.published_at %}{{ post.published_at.strftime('%d.%m.%Y') }}{% endif %}</span>
            <div>
                <h3><a href="/posts/{{ post.slug }}">{{ post.title }}</a></h3>
                {% if post.excerpt %}<p class="dek line-clamp-2">{{ post.excerpt }}</p>{% endif %}
            </div>
            <span class="pull">
                {% if post.visibility.value != 'public' %}<span class="tag tag-accent">Для своих</span>{% endif %}
                <span class="meta num">{{ post.view_count }} просмотров</span>
            </span>
        </article>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <p>Ничего не найдено</p>
        <p class="meta">Попробуйте другие ключевые слова</p>
    </div>
    {% endif %}
{% else %}
<div class="empty-state">
    <p>Введите запрос для поиска</p>
</div>
{% endif %}
```

- [ ] **Step 2: Replace `templates/pages/search.html` entirely**

```html
{% extends "base.html" %}

{% block title %}Поиск{% endblock %}

{% block content %}
<section class="section" style="border-top: 0;">
    <div class="article-col">
        <div class="section-head" data-reveal>
            <p class="kicker">Архив</p>
            <h1 style="font-size: var(--fs-h2);">Поиск</h1>
        </div>

        <form action="/search" method="GET" style="margin-bottom: 40px;" data-reveal>
            <input type="text"
                   name="q"
                   value="{{ query }}"
                   placeholder="Введите запрос…"
                   class="field field-lg"
                   autofocus
                   hx-get="/partials/search-results"
                   hx-trigger="keyup changed delay:300ms"
                   hx-target="#search-results"
                   hx-include="[name='q']">
        </form>

        <div id="search-results">
            {% if query %}
                {% if posts %}
                <p class="meta" style="margin-bottom: 20px;">Найдено: {{ total }}</p>
                <div>
                    {% for post in posts %}
                    <article class="log-row">
                        <span class="meta num">{% if post.published_at %}{{ post.published_at.strftime('%d.%m.%Y') }}{% endif %}</span>
                        <div>
                            <h3><a href="/posts/{{ post.slug }}">{{ post.title }}</a></h3>
                            {% if post.excerpt %}<p class="dek line-clamp-2">{{ post.excerpt }}</p>{% endif %}
                        </div>
                        <span class="pull">
                            {% if post.visibility.value != 'public' %}<span class="tag tag-accent">Для своих</span>{% endif %}
                            <span class="meta num">{{ post.view_count }} просмотров</span>
                        </span>
                    </article>
                    {% endfor %}
                </div>

                {% if has_more %}
                <div style="text-align: center; margin-top: 32px;">
                    <a href="/search?q={{ query }}&page={{ page + 1 }}" class="btn btn-secondary">Загрузить ещё</a>
                </div>
                {% endif %}
                {% else %}
                <div class="empty-state">
                    <p>Ничего не найдено</p>
                    <p class="meta">Попробуйте другие ключевые слова</p>
                </div>
                {% endif %}
            {% else %}
            <div class="empty-state">
                <p>Введите запрос для поиска</p>
            </div>
            {% endif %}
        </div>
    </div>
</section>
{% endblock %}
```

- [ ] **Step 3: Verify**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/search` → Expected: `200`
Run: `curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8000/partials/search-results?q=test'` → Expected: `200`

- [ ] **Step 4: Commit**

```bash
git add templates/pages/search.html templates/partials/search_results.html
git commit -m "feat(redesign): search page and live results" -m "<trailer>"
```

---

### Task 10: Login + auth fragments + profile

**Files:**
- Rewrite: `templates/pages/login.html`
- Modify: `src/api/v1/auth.py:181-190` and `:217-224` (two HTML fragments)
- Rewrite: `templates/pages/profile.html`

- [ ] **Step 1: Replace `templates/pages/login.html` entirely**

```html
{% extends "base.html" %}

{% block title %}Вход{% endblock %}

{% block content %}
<div class="narrow-col" style="padding-block: 96px;">
    <div style="text-align: center; margin-bottom: 40px;" data-reveal>
        <p class="kicker">Без пароля</p>
        <h1 style="font-size: var(--fs-h2);">Вход</h1>
        <p class="dek" style="margin-top: 8px;">Через Telegram-бот</p>
    </div>

    <div id="login-form" data-reveal>
        <div class="steps">
            <div class="step">
                <span class="n">1</span>
                <p>Откройте Telegram и отправьте <code style="font-family: var(--font-mono); background: var(--fg-soft); padding: 2px 6px; border-radius: 6px;">/login</code> боту <a href="https://t.me/iacob_blog_bot" target="_blank" class="linklike">@iacob_blog_bot</a></p>
            </div>
            <div class="step">
                <span class="n">2</span>
                <p>Введите полученный код ниже</p>
            </div>
        </div>

        <form hx-post="/api/v1/auth/verify-by-code"
              hx-target="#login-form"
              hx-swap="innerHTML">
            {% if next %}
            <input type="hidden" name="next" value="{{ next }}">
            {% endif %}
            <input type="text"
                   id="code"
                   name="code"
                   placeholder="ABC12345"
                   pattern="[A-Za-z0-9]{8}"
                   maxlength="8"
                   class="field code-input"
                   required>
            <button type="submit" class="btn btn-primary btn-block" style="margin-top: 16px;">Войти</button>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Restyle the two HTML fragments in `src/api/v1/auth.py`**

In `verify_by_code_only`, replace the error fragment (currently `<div class="p-4 bg-red-50 …">`):

```python
        return HTMLResponse(
            content="""
            <div class="notice notice-error">
                Неверный или просроченный код. Пожалуйста, получите новый код у бота.
            </div>
            <a href="/login" class="linklike">Попробовать снова</a>
            """,
            status_code=200,
        )
```

And the success fragment (currently `<div class="p-4 bg-green-50 …">`):

```python
    html_response = HTMLResponse(
        content=f"""
        <div class="notice notice-success">
            Добро пожаловать, {user.display_name}! Перенаправление...
        </div>
        """,
        status_code=200,
    )
```

- [ ] **Step 3: Replace `templates/pages/profile.html` entirely**

(All Jinja logic — thresholds list, progress computation, achievements sort — is preserved; only presentation changes.)

```html
{% extends "base.html" %}

{% block title %}Профиль{% endblock %}

{% block content %}
<div class="narrow-col" style="padding-block: 80px;">
    <div class="profile-head" data-reveal>
        <div class="ava">{{ user.display_name[0] | upper }}</div>
        <h1 style="font-size: var(--fs-h2);">{{ user.display_name }}</h1>
        <p class="meta" style="margin-top: 4px;">@{{ user.username or 'не указан' }}</p>
    </div>

    {% if error %}
    <div class="notice notice-error">{{ error }}</div>
    {% endif %}

    {% if success %}
    <div class="notice notice-success">{{ success }}</div>
    {% endif %}

    <form method="post" action="/profile/update-nickname" data-reveal>
        <label for="display_name" class="form-label">Ваш ник</label>
        <input type="text"
               id="display_name"
               name="display_name"
               value="{{ user.display_name }}"
               maxlength="128"
               class="field"
               required>
        <button type="submit" class="btn btn-primary btn-block" style="margin-top: 12px;">Сохранить</button>
    </form>

    <hr class="divider">

    <div data-reveal>
        <div class="stat-row">
            <span class="k">Уровень</span>
            <span class="num" style="font-weight: 700;">{{ user.level }}</span>
        </div>
        <div style="margin-block: 8px;">
            <div class="stat-row" style="padding-block: 0 6px;">
                <span class="k num">XP: {{ user.xp }}</span>
                {% set thresholds = [0, 15, 40, 75, 125, 200, 300, 425, 575, 750, 1000] %}
                {% if user.level < thresholds|length - 1 %}
                <span class="k num">{{ thresholds[user.level + 1] }}</span>
                {% else %}
                <span class="k">MAX</span>
                {% endif %}
            </div>
            <div class="xp-bar">
                {% if user.level < thresholds|length - 1 %}
                {% set current_threshold = thresholds[user.level] %}
                {% set next_threshold = thresholds[user.level + 1] %}
                {% set progress = ((user.xp - current_threshold) / (next_threshold - current_threshold) * 100) | int %}
                <div style="width: {{ [progress, 100] | min }}%"></div>
                {% else %}
                <div style="width: 100%"></div>
                {% endif %}
            </div>
        </div>
        <div class="stat-row">
            <span class="k">Уровень доступа</span>
            <span>
                {% if user.access_level.name == 'PUBLIC' %}Гость
                {% elif user.access_level.name == 'REGISTERED' %}Зарегистрированный
                {% elif user.access_level.name == 'PREMIUM_1' %}Premium
                {% elif user.access_level.name == 'PREMIUM_2' %}Premium+
                {% endif %}
            </span>
        </div>
    </div>

    {% if user.achievements %}
    <hr class="divider">
    <div data-reveal>
        <p class="form-label">Достижения</p>
        {% for ach in user.achievements | sort(attribute='level') %}
        <div class="ach-row">
            {% if ach.image_path %}
            <img src="/uploads/{{ ach.image_path }}" alt="{{ ach.title }}">
            {% else %}
            <div class="ach-ph">{{ ach.level }}</div>
            {% endif %}
            <div>
                <h4>{{ ach.title }}</h4>
                <p>{{ ach.description[:80] }}{% if ach.description|length > 80 %}…{% endif %}</p>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <hr class="divider">
    <div style="text-align: center;">
        <a href="/api/v1/auth/logout" class="linklike" style="color: var(--err); font-size: 14px;">Выйти из аккаунта</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Verify**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/login` → Expected: `200`
Run: `curl -s http://localhost:8000/login | grep -c 'code-input'` → Expected: `1`
Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/profile` → Expected: `302` (unauthenticated redirect; confirms no template error at import)
Run: `curl -s -X POST http://localhost:8000/api/v1/auth/verify-by-code -d 'code=WRONG123' | grep -c 'notice-error'` → Expected: `1`

- [ ] **Step 5: Commit**

```bash
git add templates/pages/login.html templates/pages/profile.html src/api/v1/auth.py
git commit -m "feat(redesign): login and profile pages, in-system auth notices" -m "<trailer>"
```

---

### Task 11: Cleanup + full verification sweep

**Files:**
- Delete: `templates/partials/gallery_grid.html` (orphaned: no route renders it; it references a non-existent `/partials/gallery` endpoint)

- [ ] **Step 1: Delete the orphaned partial**

```bash
git rm templates/partials/gallery_grid.html
```

- [ ] **Step 2: Route sweep**

```bash
for p in / /gallery /works /search /login "/partials/posts" "/partials/search-results?q=x"; do
  printf '%-40s' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000$p"
done
```
Expected: all `200`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/admin   # 302 (auth redirect)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/profile # 302 (auth redirect)
```

- [ ] **Step 3: No Tailwind remnants on public pages**

```bash
for p in / /gallery /works /search /login; do
  echo -n "$p: "; curl -s "http://localhost:8000$p" | grep -cE 'cdn\.tailwindcss|text-gray-|rounded-2xl|bg-gray-'
done
```
Expected: all `0`.

```bash
grep -c 'cdn.tailwindcss.com' templates/admin_base.html
```
Expected: `1` (admin keeps its frozen base).

- [ ] **Step 4: Visual pass (human or browser tooling)**

Check in a real browser at desktop and ~375px width: home (reveal cascade, pinned card, log rows), a post page (progress thread grows on scroll), gallery masonry, login form. Emulate `prefers-reduced-motion: reduce` in devtools — reveals and transitions must be instant. This step is a REQUIRED gate before the final commit; report anything broken instead of committing over it.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(redesign): remove orphaned gallery_grid partial" -m "<trailer>"
```

---

## Self-review notes (already applied)

- **Spec coverage:** design system (T1), animations incl. reduced-motion/View Transitions (T1/T2/T4), home journal composition (T5), post page + amber progress (T6), gallery (T7), works (T8), search (T9), login/profile (T10), admin untouched-but-decoupled (T3), htmx flows preserved (T5/T6/T9), missing-data fallbacks (empty states in T5/T7/T8/T9; pinned card only when `posts[0].is_pinned`).
- **Deviation from spec:** spec said "no backend changes"; two exceptions approved during planning because the spec's own features require them: `recent_images` context in the home route (gallery strip) and two presentation-only HTML strings in `auth.py` (they render inside the redesigned login page). No logic changes.
- **Type consistency:** class names used in templates all exist in `site.css` (checked: `pinned`, `log-row`, `pull`, `thumb-strip`, `doc-chip`, `feed-sentinel`, `spinner`, `empty-state`, `gallery-strip`, `masonry`, `tile`, `tile-ph`, `tile-caption`, `prose`, `media-list`, `media-block`, `pdf-viewer`, `pdf-pages`, `pdf-error`, `comments`, `comment`, `ava`, `actions`, `comment-replies`, `reply-form-container`, `hidden`, `field`, `field-lg`, `code-input`, `form-label`, `form-hint`, `notice*`, `steps`, `step`, `profile-head`, `stat-row`, `xp-bar`, `ach-row`, `divider`, `narrow-col`, `linklike`, `progress`, `data-reveal`/`is-visible`/`has-reveal`).
