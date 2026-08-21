# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** AiSummryIO
**Category:** No-code / Low-code Builder
**Design Dials:** Variance 4/10 (Balanced / Modern) | Motion 3/10 (Subtle) | Density 7/10 (Standard)

> **Source of truth:** the tokens below mirror the `:root` block in
> `frontend/src/styles/globals.css`. That file is authoritative — if the two
> disagree, fix this document.

---

## Global Rules

### Color Palette

Warm, paper-like. Cream ground, terracotta accent, warm near-black text.
Depth comes from borders and generous space, **not** elevation and glow.

| Role | Light | Dark | CSS Variable |
|------|-------|------|--------------|
| Background | `#F5F4EE` | `#1F1E1D` | `--bg` |
| Surface | `#FFFFFF` | `#262624` | `--surface` |
| Surface (raised) | `#FAF9F5` | `#2D2C2A` | `--surface-2` |
| Text | `#1F1E1D` | `#F5F4EE` | `--text` |
| Text muted | `#726F66` | `#A6A29A` | `--text-muted` |
| Border | `#E5E2D9` | `#3A3937` | `--border` |
| Primary | `#A94F32` | `#E08A6B` | `--primary` |
| Primary action | `#B8563C` | `#D97757` | `--primary-action` |
| Sidebar | `#262624` | `#1A1917` | `--sidebar` |
| Success | `#42704F` | `#7FAE87` | `--success` |
| Warning | `#946619` | `#D9A94E` | `--warning` |
| Destructive | `#B3402F` | `#E07A63` | `--danger` |

**Color Notes:** Terracotta is the single accent — there is no secondary hue,
and cyan/violet pairings do not belong in this theme.

Light mode runs the terracotta **darker than the `#D97757` brand tone**, and
this is deliberate: `--primary` and `--primary-action` carry text and icons,
so each is tuned to clear **4.5:1** on both `--bg` and `--surface` (white on
`#B8563C` is 4.74:1; `#D97757` would be only 3.12:1 and fails). The lighter
`#D97757` survives in `--brand-gradient` and `--brand-glow`, which are
decorative fills behind large shapes rather than text backgrounds.

Every light-mode pair above is verified against WCAG AA. Re-check with a
contrast tool before changing any of these values.

### Typography

- **Heading Font:** Noto Sans Hebrew
- **Body Font:** Noto Sans Hebrew
- **Mood:** hebrew, modern, RTL, clean, professional, readable
- **Google Fonts:** [Noto Sans Hebrew + Noto Sans Hebrew](https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew:wght@300;400;500;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew:wght@300;400;500;700&display=swap');
```

### Spacing Variables

*Density: 7/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Token | Value (light) | Usage |
|-------|---------------|-------|
| `--shadow-soft` | `0 1px 3px rgba(31,30,29,0.06)` | Cards, section surfaces |
| `--shadow` | `0 18px 48px rgba(31,30,29,0.10)` | Modals, dropdowns, popovers |
| `--brand-glow` | `0 1px 2px rgba(31,30,29,0.10)` | Primary action only |

Shadows are deliberately quiet. Prefer a `1px solid var(--border)` to a
shadow when separating two surfaces.

---

## Component Specs

### Buttons

Always reference tokens, never literals — that is what keeps light and dark
in sync from one place.

```css
/* Primary Button */
.btn-primary {
  background: var(--primary-action);
  color: #fff;
  padding: 12px 24px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: var(--brand-glow);
  transition: background-color 200ms ease, box-shadow 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  background: var(--primary-action-hover);
}

/* Secondary Button */
.btn-secondary {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border-strong);
  padding: 12px 24px;
  border-radius: 12px;
  font-weight: 600;
  transition: background-color 200ms ease, border-color 200ms ease;
  cursor: pointer;
}

.btn-secondary:hover {
  background: var(--surface-2);
  border-color: var(--primary);
}
```

### Cards

```css
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow-soft);
  transition: border-color 200ms ease;
}

.card:hover {
  border-color: var(--border-strong);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  font-size: 16px;
  transition: border-color 200ms ease, box-shadow 200ms ease;
}

.input:focus-visible {
  border-color: var(--primary);
  outline: none;
  box-shadow: var(--focus);
}
```

### Modals

```css
.modal-overlay {
  background: rgba(31, 30, 29, 0.78);
  backdrop-filter: blur(12px);
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Warm Editorial (paper and ink)

**Keywords:** cream, terracotta, warm neutral, paper, calm, readable, generous
whitespace, hairline borders, restrained, text-first, quiet

**Best For:** Reading-heavy AI tools, research and summary interfaces,
document workspaces, professional Hebrew/RTL products

**Key Effects:** Flat background — no ambient blobs or colour wash. Separation
comes from `1px` borders and space. Translucent blur is allowed **only** on
sticky headers and modal scrims, never as decoration, and never with a
`saturate()` boost (it skews terracotta toward orange). Transitions are
150–300ms `ease` on colour and border, not on layout.

### Page Pattern

**Pattern Name:** Workspace / Answer First

This is an application shell, not a landing page: dark navigation rail, a
bounded reading column, and a bottom composer.

- **Reading column:** the answer comes first and owns the widest, quietest
  space on the page. Supporting detail sits below it, never beside it.
- **Progressive disclosure:** summary → sections → raw evidence on demand.
- **RTL:** Hebrew is primary. Use logical properties (`inset-inline-start`,
  `padding-inline`) so the layout mirrors correctly. IDs, URLs, JSON, and
  model names stay LTR inside an RTL page.

---

## Motion

Motion is 3/10 — it confirms an action, it is never decoration. No scroll
reveals, no ambient oscillation, no GSAP.

- Colour, border, and opacity transitions at 150–300ms `ease`.
- Entrances (modals, drawers) fade with an 8–12px offset, ~200ms.
- Never animate layout-affecting properties on hover.
- Every animation must be disabled under `prefers-reduced-motion: reduce`.

---

## Anti-Patterns (Do NOT Use)

- ❌ **A second accent hue** — terracotta is the only accent; no violet/cyan
- ❌ **Glow, ambient blobs, or decorative glassmorphism** — depth is borders
- ❌ **Heavy drop shadows** — prefer a hairline border
- ❌ **Hardcoded hex in components** — always reference a token
- ❌ **Pure `#000` or pure cool grey** — neutrals are warm

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
