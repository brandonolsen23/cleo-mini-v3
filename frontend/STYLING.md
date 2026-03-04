# Frontend Styling Guide

This app replicates the WorkOS dashboard design system. All styling decisions
are centralized in three files. **Do not add ad-hoc styles** — use the tokens
and patterns below.

## Architecture

```
tailwind.config.js   — Font family, font weight remapping
src/lib/theme.ts     — Radix Theme props, chart colors, design system docs
src/index.css        — @font-face, CSS custom properties, Radix overrides
```

## Changing the accent color

Edit `src/lib/theme.ts`:

1. Change `THEME.accentColor` (e.g., `"jade"` → `"blue"`)
2. Update `CHART_COLORS.primary` array to use matching `--{color}-11/9/7/4` tokens
3. That's it — all `--accent-*` vars update automatically via Radix

Available Radix colors: `tomato`, `red`, `ruby`, `crimson`, `pink`, `plum`,
`purple`, `violet`, `iris`, `indigo`, `blue`, `cyan`, `teal`, `jade`, `green`,
`grass`, `lime`, `mint`, `sky`, `yellow`, `amber`, `orange`, `brown`.

## Typography

**Font:** Untitled Sans (Klim Type Foundry), loaded via `@font-face` in `index.css`.

**Weights — only two are used in the UI:**

| Tailwind class  | CSS value | Font file    | Usage                           |
|-----------------|-----------|--------------|----------------------------------|
| `font-normal`   | 400       | Regular      | Body text, inactive nav items    |
| `font-medium`   | 500       | Medium       | Headings, emphasis, active nav   |
| `font-semibold` | 500       | Medium       | Remapped — same as font-medium   |
| `font-bold`     | 500       | Medium       | Remapped — same as font-medium   |

The Bold (700) font file is registered but **never used**. WorkOS's "bold" is
actually Medium weight. The remapping lives in `tailwind.config.js` so you can
write `font-bold` and it renders as 500.

Radix `<Heading>` components default to 500 via the `.rt-Heading` override in
`index.css`.

**Do not:**
- Use `fontWeight: 700` in inline styles
- Use Radix `weight="bold"` on Heading/Text (it bypasses the remap — use `weight="medium"`)
- Add new `@font-face` entries without updating this doc

## Colors

**Grays:** Always use Radix `--gray-N` (1-12) or `--gray-aN` (alpha variants)
tokens. The gray scale is "slate" — cool grays with a subtle blue tint on P3
displays.

**Accent:** Use `--accent-N` for theme-aware accent colors. Use `--{color}-N`
(e.g., `--jade-9`) only in `CHART_COLORS` or when you need a specific named color.

**Semantic:**
- Positive/success: `--green-11` (text), `--green-9` (fill)
- Negative/error: `--red-11` (text), `--red-9` (fill)
- Neutral: `--gray-8`

**Do not:**
- Hardcode hex colors (`#4b814f`) — use Radix tokens
- Use `rgba()` for grays — use `--gray-aN` alpha tokens
- Invent new color variables — check Radix's palette first

### Gray scale quick reference

| Token       | Usage                                       |
|-------------|---------------------------------------------|
| `--gray-1`  | Page background                             |
| `--gray-2`  | Sidebar background, subtle surface          |
| `--gray-3`  | Hover backgrounds                           |
| `--gray-4`  | Subtle borders, dividers                    |
| `--gray-6`  | Card borders, input borders                 |
| `--gray-7`  | Stronger input borders                      |
| `--gray-8`  | Neutral chart fill                          |
| `--gray-9`  | Muted text (descriptions, secondary labels) |
| `--gray-11` | Secondary text, inactive nav, icons         |
| `--gray-12` | Primary text, headings                      |

## Cards

Every card uses the same pattern:

```tsx
<div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
  {/* content */}
</div>
```

- Radius: `var(--card-radius)` = 12px (defined in `:root`)
- Border: `var(--gray-6)`
- Padding: `p-5` (20px) — standard for all cards
- Inner dividers: `border-[var(--gray-4)]`

**Do not** use `p-4`, `p-6`, or `p-8` for card padding. Use `p-5`.

## Spacing

| Scale   | Tailwind | Usage                          |
|---------|----------|--------------------------------|
| Section | `gap-6`  | Between major page sections    |
| Grid    | `gap-4`  | Between cards in a grid row    |
| Inner   | `gap-2`  | Between elements inside a card |

## Borders & Radius

| Token                   | Value | Usage                    |
|-------------------------|-------|--------------------------|
| `var(--card-radius)`    | 12px  | Cards, major containers  |
| `var(--radius-2)`       | Radix | Buttons, pills, inputs   |
| `var(--radius-3)`       | Radix | Tooltips, dropdowns      |

`--radius-2/3/4` are provided by Radix Themes at runtime (not in `:root`).
They adapt to the `THEME.radius` setting ("medium").

## Shadows

Four elevation levels defined in `:root`:

```css
--elevation-1   /* subtle outline */
--elevation-2   /* card hover */
--elevation-3   /* dropdown / popover */
--elevation-4   /* modal / dialog */
```

## Sidebar nav tokens

Defined in `.app-sidebar` in `index.css`:

| Token                  | Value            | Usage                   |
|------------------------|------------------|-------------------------|
| `--nav-text-inactive`  | `--gray-11`      | Unselected nav text     |
| `--nav-text-active`    | `--gray-12`      | Selected nav text       |
| `--nav-icon-inactive`  | `--gray-a9`      | Unselected nav icon     |
| `--nav-icon-active`    | `--gray-a9`      | Selected nav icon       |
| `--nav-active-bg`      | `--gray-a4`      | Selected row background |
| `--nav-hover-bg`       | `--gray-a3`      | Hover row background    |

Nav item font weights: 400 inactive, 500 active (set in `Sidebar.tsx`).

## Layout

| Token              | Value | Usage              |
|--------------------|-------|--------------------|
| `--sidebar-width`  | 220px | Left navigation    |
| `--header-height`  | 56px  | Top header bar     |

Grid is defined in `.app-layout` in `index.css`.

## Checklist for new components

1. Text color → `text-[var(--gray-12)]` or `text-[var(--gray-9)]`
2. Font weight → `font-medium` for emphasis, `font-normal` for body
3. Borders → `border-[var(--gray-6)]` for cards, `border-[var(--gray-4)]` for dividers
4. Radius → `rounded-[var(--card-radius)]` for cards
5. Padding → `p-5` inside cards
6. Gaps → `gap-6` sections, `gap-4` grids, `gap-2` inner
7. Accent colors → `var(--accent-9)` not hardcoded color names
8. Hover states → `hover:bg-[var(--gray-a3)]`
9. No `fontWeight: 700`, no hardcoded hex, no `rgba()` grays
