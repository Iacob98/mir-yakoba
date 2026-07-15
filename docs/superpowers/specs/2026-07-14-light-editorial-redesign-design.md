# Light Editorial Redesign — Design Spec

Date: 2026-07-14
Status: approved by user (brainstorming session)

## Goal

Full visual redesign of all public pages of «Мир Якоба» in a light editorial
("magazine/paper") style with restrained micro-animations. Replaces the current
Tailwind-CDN light theme. The dark mockups (`redesign-home-v2.html`,
`redesign-post-v2.html`) contribute structure and components, re-colored onto
paper; their dark palette is **not** used.

Decisions made with the user:

| Question | Decision |
|---|---|
| Visual direction | B — light editorial (not the dark v2 palette, not dual-theme) |
| Scope | All public pages; admin panel untouched |
| Animation level | A — restrained micro-animations |
| Home composition | A — "journal": pinned card + date-led log feed (structure from v2 mockup) |
| Typography/accent | B — Literata display serif + amber accent |
| Tech approach | Hand-written CSS design system; remove Tailwind CDN entirely |

## Non-goals

- No dark theme / theme toggle (amber accent deliberately keeps a bridge to the
  v2 "evening lamp" mockup if a dark theme is added later as a separate project).
- No admin panel restyling (verify it does not depend on `base.html` classes).
- No backend/model/API changes — templates and static assets only.
- No JS frameworks or animation libraries.

## Design system (`static/css/site.css`)

One stylesheet, structured like the v2 mockup: tokens first, then base, then
semantic component classes. Loaded from `base.html`, replacing: Tailwind CDN
script + inline `tailwind.config`, Inter/Playfair Google-Fonts link, and the
inline `<style>` blocks.

**Tokens (`:root`):**
- Paper background `#fbf8f1`; white card surface; ink text `#211d16`;
  muted `#5b5344`; hairline borders; amber accent `#a16207`
  (kickers, hover states, primary CTA). Accent used sparingly — roughly twice
  per screen, following the v2 critique discipline.
- Fluid type scale via `clamp()` (h1 ~30–54px), spacing scale, container
  `1080px`, radii — carried over from the v2 mockup tokens.

**Fonts:**
- **Literata** (Google Fonts, Cyrillic subset, weights 700 + italic) for
  display headings.
- System sans stack for body text, 16–17px / 1.65.
- Monospace stack for dates, meta lines, kickers, tags (v2 device, kept).

**Components** (ported from v2 mockups, re-colored to paper):
`.topnav` (sticky, blurred paper glass), `.pinned` card, `.log-row`
(date | title+dek | tag+views grid), `.thumb-strip`, `.doc-chip`,
`.gallery-strip`, `.btn` family (primary = amber, secondary = hairline,
ghost/arrow), `.tag`, `.kicker`, `.meta`/`.num`, masonry gallery,
`.prose` styles for Editor.js-rendered content (Literata subheads, amber
blockquote rule — device from the v2 post mockup).

**A11y baseline from v2:** skip-link, `:focus-visible` outline in accent,
44px touch targets, `prefers-reduced-motion` kill-switch.

## Pages

- **Home** (`pages/home.html` + `partials/posts_list.html`): hero (kicker,
  Literata h1 + lead from SiteSettings, avatar) → pinned post card (first
  `is_pinned` post; model and sort order already support this) → log feed:
  `.log-row` per post — mono date, title, excerpt, post-type tag, view count;
  photo posts show a `.thumb-strip` of attached images, document posts a
  `.doc-chip` → gallery strip (4 recent works) → author block with «Войти
  через Telegram» CTA (hidden for logged-in users). htmx infinite scroll kept.
- **Post** (`pages/post_detail.html`): ~68ch column, large Literata title,
  mono meta line, amber reading-progress thread at top, `.prose` content,
  comments restyled in-system.
- **Gallery**: masonry kept, new tokens; mono captions; amber hover border.
- **Works / Search / Login / Profile**: reflowed into the same system —
  journal section headings, search results as log rows, login code input as
  large mono field.
- **htmx partials** (`posts_list`, `search_results`, `comments_list`,
  `comment`, `gallery_grid`, `media_item`): rewritten to system classes; all
  styling comes from `site.css` so fragments render identically on first load
  and on swap.

## Animation layer (level A — restrained)

- **Scroll reveal:** sections and log rows fade-up with ~60ms stagger;
  `IntersectionObserver` (~15 lines vanilla JS) watching `[data-reveal]`;
  htmx-inserted content re-observed (via `htmx:afterSettle`).
- **Hovers:** left-to-right link underline, `→` shift on arrow buttons, images
  `scale(1.03)`, cards lift shadow.
- **Reading progress:** CSS `animation-timeline: scroll()` with a small JS
  fallback where unsupported.
- **Page transitions:** cross-fade via View Transitions API
  (`@view-transition` rule) as progressive enhancement.
- **`prefers-reduced-motion: reduce`** disables all of the above.

Total custom JS: mobile menu toggle, reveal observer, progress fallback.
No libraries beyond the existing htmx.

## Error handling / robustness

- Pages must render correctly when data is missing: no pinned post → skip the
  pinned card; post without images/documents → plain log row; empty gallery →
  hide strip section.
- View Transitions and scroll-driven animations are progressive enhancements;
  no functional dependency on them.
- htmx fragments carry no page-level assumptions (styles live in `site.css`).

## Verification

- All public routes return 200 on the running dev stack; visual pass via
  browser screenshots (desktop + mobile width).
- htmx flows: infinite scroll, search-as-you-type, comment post/render.
- `prefers-reduced-motion` honored (emulate in devtools).
- Admin pages unaffected (spot-check `/admin`).
- Existing `pytest` suite still passes (no backend changes expected).

## Out-of-repo artifacts

Brainstorm mockups live in `.superpowers/brainstorm/` (gitignored). The old
root-level `redesign-*.html` mockups and `critique.json` remain untouched as
reference; they may be deleted after implementation.
