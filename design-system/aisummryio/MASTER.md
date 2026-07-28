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
| Text muted | `#7D7A70` | `#A6A29A` | `--text-muted` |
| Border | `#E5E2D9` | `#3A3937` | `--border` |
| Primary | `#C25F3F` | `#E08A6B` | `--primary` |
| Primary action | `#D97757` | `#D97757` | `--primary-action` |
| Sidebar | `#262624` | `#1A1917` | `--sidebar` |
| Success | `#4A7C59` | `#7FAE87` | `--success` |
| Warning | `#A1701C` | `#D9A94E` | `--warning` |
| Destructive | `#B3402F` | `#E07A63` | `--danger` |

**Color Notes:** Terracotta `#D97757` is the single accent. There is no
secondary hue — cyan/violet pairings do not belong in this theme. `--primary`
is darkened in light mode so text and icons using it clear 4.5:1 on cream.

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
| `--shadow-soft` | `0 2px 8px rgba(31,30,29,0.05)` | Cards, section surfaces |
| `--shadow` | `0 12px 32px rgba(31,30,29,0.09)` | Modals, dropdowns, popovers |
| `--brand-glow` | `0 6px 18px rgba(217,119,87,0.22)` | Primary action only |

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

**Style:** Modern Dark (Cinema Mobile)

**Keywords:** dark mode, cinematic, ambient light, glassmorphism, deep black, indigo, glow, blur, atmospheric, reanimated, haptic, premium, layered, frosted glass, linear gradient

**Best For:** Developer tools, pro productivity apps, fintech/trading dashboards, media/streaming platforms, AI tool interfaces, high-end gaming companion apps

**Key Effects:** Expo.out Bezier(0.16,1,0.3,1) easing; spring modals (damping:20 stiffness:90); haptic-linked press (Impact Light/Medium); animated ambient light blobs (Reanimated translateX/Y slow oscillation); BlurView glassmorphism headers/nav (intensity 20); scale press 0.97 → 1.0; avoid pure #000000 (OLED smear)

### Page Pattern

**Pattern Name:** Newsletter / Content First

- **Conversion Strategy:** Single field form (Email only). Show 'Join X, 000 readers'. Read sample link.
- **CTA Placement:** Hero inline form + Sticky header form
- **Section Order:** 1. Hero (Value Prop + Form), 2. Recent Issues/Archives, 3. Social Proof (Subscriber count), 4. About Author

---

## Motion

**Scroll Reveal** (Subtle) — Trigger: scroll (viewport enter) | Duration: 300-400ms | Easing: `power1.out`

```js
gsap.from(el, { opacity: 0, y: 12, duration: 0.35, ease: 'power1.out', scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none reverse' } });
```

**Framework notes:** Requires the ScrollTrigger plugin registered once via gsap.registerPlugin(ScrollTrigger)

- ✅ Keep the y offset small (8-16px) so it reads as a fade, not a slide
- ❌ Don't reveal below-the-fold content needed for SEO/crawlers as invisible-by-default without a no-JS fallback
- ⚡ toggleActions 'play none none reverse' avoids re-triggering on every scroll direction change

---

## Anti-Patterns (Do NOT Use)

- ❌ Flat design without depth
- ❌ Text-heavy pages

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
