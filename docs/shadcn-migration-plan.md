# shadcn/ui Migration Plan

## Target Configuration

| Setting | Value |
|---------|-------|
| Component Library | Radix UI |
| Style | Mira |
| Base Color | Neutral |
| Theme | Neutral |
| Icon Library | Lucide (already installed) |
| Font | JetBrains Mono |
| Radius | None (0rem) |
| Menu Color | Default |
| Menu Accent | Subtle |

## Current Stack (No Changes Needed)

These stay as-is:
- React 18.3.1 + TypeScript 5.7.3
- Vite 6.0.7 (build tool)
- TanStack Table 8.21.2 + TanStack Virtual 3.11.3
- lucide-react 0.468.0 (already shadcn's default)
- mapbox-gl 3.18.1 + react-map-gl 8.1.0
- react-router-dom 7.1.1

## Phase 0: Setup (~15 min)

### 0a. Install shadcn CLI and initialize

```bash
cd frontend
npx shadcn@latest init
```

When prompted, select:
- Style: **Mira** (or "New York" if Mira isn't available in CLI -- then apply Mira theme manually)
- Base color: **Neutral**
- CSS variables: **Yes**
- Border radius: **0rem** (None)

This will:
- Create `components.json` config file
- Update `tailwind.config.js` with shadcn theme extensions (CSS variable colors)
- Update `src/index.css` with CSS variable definitions for light/dark themes
- Create `src/lib/utils.ts` with the `cn()` utility

### 0b. Add path alias to tsconfig.json

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### 0c. Update vite.config.ts

```typescript
import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../cleo/web/static/app",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8099",
    },
  },
});
```

### 0d. Install JetBrains Mono font

```bash
npm install @fontsource/jetbrains-mono
```

Then in `src/main.tsx`:

```typescript
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";
import "@fontsource/jetbrains-mono/700.css";
```

And in `tailwind.config.js`, extend fontFamily:

```javascript
theme: {
  extend: {
    fontFamily: {
      mono: ['"JetBrains Mono"', 'monospace'],
      sans: ['"JetBrains Mono"', 'monospace'], // use mono as default
    },
  },
},
```

### 0e. Add core shadcn components

```bash
npx shadcn@latest add button card badge input textarea checkbox sheet table popover separator
```

This creates files in `src/components/ui/` -- one file per component, fully editable.

---

## Phase 1: Low-Hanging Fruit (~45 min)

### 1a. Buttons (all files, ~50 instances)

**Current pattern (repeated everywhere):**
```tsx
<button
  onClick={handler}
  disabled={condition}
  className="px-4 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-blue-600 text-white hover:bg-blue-700"
>
  Save
</button>
```

**Replace with:**
```tsx
import { Button } from "@/components/ui/button";

<Button onClick={handler} disabled={condition}>
  Save
</Button>
```

Variant mapping:
- Blue primary buttons -> `<Button>` (default variant)
- Gray/outline buttons -> `<Button variant="outline">`
- Ghost/icon buttons -> `<Button variant="ghost" size="icon">`
- Destructive/red buttons -> `<Button variant="destructive">`

**Files to update:** DataIssueCard.tsx, Pagination.tsx, MultiSelect.tsx, all detail pages, all list pages.

### 1b. Cards (detail pages)

**Current pattern:**
```tsx
<div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
  <div className="px-5 py-3 border-b border-gray-100">
    <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Title</h2>
  </div>
  <div className="px-5 py-4">
    {/* content */}
  </div>
</div>
```

**Replace with:**
```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle className="text-sm uppercase tracking-wider">Title</CardTitle>
  </CardHeader>
  <CardContent>
    {/* content */}
  </CardContent>
</Card>
```

**Files to update:** TransactionDetailPage.tsx, PropertyDetailPage.tsx, PartyDetailPage.tsx, ContactDetailPage.tsx, DataIssueCard.tsx.

### 1c. BrandBadge -> Badge

**Current:** Custom `<span>` with inline Tailwind color classes.

**Keep as-is** -- BrandBadge uses a custom soft rainbow color palette with 10 category-specific hex colors. The shadcn Badge component doesn't support arbitrary color variants. Keep the existing BrandBadge component but optionally wrap it with shadcn's Badge for consistent base styling:

```tsx
import { Badge } from "@/components/ui/badge";
// Use Badge for generic badges, keep BrandBadge for brand-specific coloring
```

### 1d. Form Inputs

**Current:**
```tsx
<input className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
<textarea className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 ..." />
<input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-blue-600 ..." />
```

**Replace with:**
```tsx
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";

<Input placeholder="Search..." />
<Textarea rows={2} placeholder="Notes" />
<Checkbox checked={value} onCheckedChange={handler} />
```

Note: shadcn Checkbox uses Radix and fires `onCheckedChange(boolean)` instead of `onChange(event)`. Update all checkbox handlers accordingly.

**Files to update:** DataIssueCard.tsx, MultiSelect.tsx, all pages with search/filter inputs.

---

## Phase 2: SlideOut -> Sheet (~30 min)

**Current:** Custom `SlideOut.tsx` (80 LOC) with manual Escape key, click-outside, body scroll lock, and CSS animation.

**Replace with shadcn Sheet** which handles all of that via Radix Dialog primitive:

```tsx
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";

<Sheet open={open} onOpenChange={onClose}>
  <SheetContent side="right" className="w-full max-w-2xl sm:max-w-2xl">
    <SheetHeader>
      <SheetTitle>{title}</SheetTitle>
      {subtitle && <SheetDescription>{subtitle}</SheetDescription>}
    </SheetHeader>
    <div className="flex-1 overflow-y-auto py-4">
      {children}
    </div>
  </SheetContent>
</Sheet>
```

Benefits: built-in focus trap, Escape handling, scroll lock, backdrop, animation. Delete the custom `animate-slide-in-right` keyframe from `index.css`.

**Files to update:**
- Delete `src/components/shared/SlideOut.tsx`
- Update all SlideOut consumers: NameEvidenceDrawer.tsx, SuggestedAffiliates.tsx, and any detail pages that use it
- Update prop interface: `open`/`onClose` -> `open`/`onOpenChange`

---

## Phase 3: MultiSelect (~45 min)

**Current:** Custom dropdown (107 LOC) with click-outside detection, checkbox list, clear button.

**Replace with shadcn Popover + Command or keep custom but restyle:**

Option A -- Popover + custom content (recommended, simpler):
```tsx
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

<Popover open={open} onOpenChange={setOpen}>
  <PopoverTrigger asChild>
    <Button variant="outline" className="min-w-[120px] justify-between">
      {displayText}
      {selected.length > 0 ? <X size={14} onClick={clear} /> : <ChevronDown size={14} />}
    </Button>
  </PopoverTrigger>
  <PopoverContent className="w-56 max-h-64 overflow-auto p-0">
    {options.map((opt) => (
      <label key={opt.value} className="flex items-center gap-2 px-3 py-1.5 hover:bg-accent cursor-pointer">
        <Checkbox checked={selected.includes(opt.value)} onCheckedChange={() => toggle(opt.value)} />
        <span className="text-sm">{opt.label}</span>
      </label>
    ))}
  </PopoverContent>
</Popover>
```

Benefits: auto-positioning, focus management, keyboard navigation (Radix Popover handles this).

Option B -- Add `cmdk` for searchable multi-select (only if filter lists get long enough to need search).

**Files to update:** Rewrite `MultiSelect.tsx`, all consumers keep the same external API.

---

## Phase 4: Tables (~60 min)

The TanStack Table logic stays 100% unchanged. Only the rendering JSX changes.

**Current:** Flex-based `<div>` grid with inline styles for column widths.

**Replace with semantic shadcn Table:**

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

<Table>
  <TableHeader>
    {table.getHeaderGroups().map((headerGroup) => (
      <TableRow key={headerGroup.id}>
        {headerGroup.headers.map((header) => (
          <TableHead
            key={header.id}
            style={{ width: header.getSize() }}
            onClick={header.column.getToggleSortingHandler()}
            className="cursor-pointer select-none"
          >
            <div className="flex items-center gap-1">
              {flexRender(header.column.columnDef.header, header.getContext())}
              {/* sorting icons unchanged */}
            </div>
          </TableHead>
        ))}
      </TableRow>
    ))}
  </TableHeader>
  <TableBody>
    {table.getRowModel().rows.map((row) => (
      <TableRow
        key={row.id}
        onClick={() => handleRowClick(row.original.rt_id)}
        className="cursor-pointer"
      >
        {row.getVisibleCells().map((cell) => (
          <TableCell
            key={cell.id}
            style={{ width: cell.column.getSize() }}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </TableCell>
        ))}
      </TableRow>
    ))}
  </TableBody>
</Table>
```

Note: if using TanStack Virtual for row virtualization, the table body needs a custom renderer. The virtualizer row height and container setup should be preserved -- just swap the inner divs to `TableRow`/`TableCell`.

**Files to update:** TransactionsPage.tsx, PropertiesPage.tsx, PartiesPage.tsx, ContactsPage.tsx, BrandsPage.tsx, KeywordsPage.tsx (any page with a table).

---

## Phase 5: Sidebar (~20 min)

**Current:** Fixed sidebar with NavLink items, active state via blue bg + blue left border.

**Restyle with shadcn conventions:**
```tsx
<NavLink
  to={item.to}
  className={({ isActive }) =>
    cn(
      "flex items-center gap-3 px-6 py-2.5 text-sm font-medium transition-colors border-l-2",
      isActive
        ? "bg-accent text-accent-foreground border-primary"
        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground border-transparent"
    )
  }
>
```

Use `cn()` utility from shadcn for conditional classes. Replace hardcoded colors (`blue-50`, `blue-700`, `gray-600`) with CSS variable tokens (`accent`, `primary`, `muted-foreground`).

---

## Phase 6: Detail Pages (~90 min)

These are the largest files and require the most mechanical work. For each detail page:

1. Replace all inline card patterns with `<Card>` / `<CardHeader>` / `<CardContent>`
2. Replace all buttons with `<Button>` variants
3. Replace all form inputs with `<Input>` / `<Textarea>` / `<Checkbox>`
4. Replace color tokens: `text-gray-500` -> `text-muted-foreground`, `bg-white` -> `bg-card`, etc.
5. Use `<Separator />` instead of `<div className="border-b border-gray-200" />`

**Files (in order of complexity):**
1. `PartyDetailPage.tsx` (25K, ~751 LOC) -- most complex, has nested cards, expandable sections
2. `PropertiesPage.tsx` (20K) -- table + filters
3. `MapPage.tsx` (19K) -- table + map, minimal UI components
4. `KeywordsPage.tsx` (18K) -- table + keyword management
5. `TransactionsPage.tsx` (18K) -- table + filters
6. `PropertyDetailPage.tsx` (15K) -- cards + transaction history
7. `NameEvidenceDrawer.tsx` (15K) -- uses SlideOut (now Sheet)
8. `PartiesPage.tsx` (13K) -- table
9. `ContactsPage.tsx` (12K) -- table
10. `TransactionDetailPage.tsx` (11K) -- cards
11. `ContactDetailPage.tsx` (10K) -- cards
12. `BrandsPage.tsx` (10K) -- table

---

## Phase 7: Color Token Migration

After components are converted, sweep all files to replace hardcoded Tailwind colors with shadcn CSS variable tokens:

| Current (hardcoded) | Replace with (CSS variable) |
|---------------------|-----------------------------|
| `bg-white` | `bg-background` or `bg-card` |
| `bg-gray-50` | `bg-muted` |
| `text-gray-900` | `text-foreground` |
| `text-gray-700` | `text-foreground` |
| `text-gray-500` | `text-muted-foreground` |
| `text-gray-400` | `text-muted-foreground` |
| `border-gray-200` | `border-border` |
| `border-gray-100` | `border-border` |
| `bg-blue-600` | `bg-primary` |
| `text-blue-700` | `text-primary` |
| `bg-blue-50` | `bg-accent` |
| `hover:bg-gray-50` | `hover:bg-accent` |
| `hover:bg-gray-100` | `hover:bg-accent` |
| `text-green-600` | `text-green-600` (keep -- semantic) |
| `text-red-600` | `text-destructive` |

**Exception:** BrandBadge category colors (arbitrary hex values) stay as-is -- they're a custom palette, not theme colors.

---

## Phase 8: Testing & Polish (~45 min)

1. Visual sweep of every page -- check spacing, colors, font rendering
2. Test all interactive components: dropdowns, drawers, checkboxes, table sorting/filtering
3. Test keyboard navigation (Sheet focus trap, Popover escape, table navigation)
4. Test responsive behavior on narrow viewports
5. Verify `npm run build` succeeds with no TS errors
6. Verify built output works when served from `cleo web`

---

## File Inventory -- What Changes Where

### New files created by shadcn
- `frontend/components.json` -- shadcn config
- `frontend/src/lib/utils.ts` -- `cn()` utility
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/ui/checkbox.tsx`
- `frontend/src/components/ui/sheet.tsx`
- `frontend/src/components/ui/table.tsx`
- `frontend/src/components/ui/popover.tsx`
- `frontend/src/components/ui/separator.tsx`

### Files deleted
- `frontend/src/components/shared/SlideOut.tsx` (replaced by Sheet)

### Files modified (every component file)
- `frontend/src/index.css` -- replaced with shadcn CSS variables
- `frontend/src/main.tsx` -- add font imports
- `frontend/tailwind.config.js` -- shadcn theme config + font
- `frontend/tsconfig.json` -- add path alias
- `frontend/vite.config.ts` -- add path alias
- All 6 shared components
- All 12 page components
- `Sidebar.tsx` -- token colors
- `AppLayout.tsx` -- token colors (if any)

### Files unchanged
- All API hooks (`src/api/*`)
- `src/App.tsx` (router config)
- `MapLink.tsx` (simple link, no UI primitives)
- `PropertyPopup.tsx` (map popup, minimal UI)

---

## Estimated Total: ~4.5 hours

| Phase | Time |
|-------|------|
| 0. Setup | 15 min |
| 1. Buttons + Cards + Inputs | 45 min |
| 2. SlideOut -> Sheet | 30 min |
| 3. MultiSelect | 45 min |
| 4. Tables | 60 min |
| 5. Sidebar | 20 min |
| 6. Detail pages | 90 min |
| 7. Color tokens | (folded into phases 1-6) |
| 8. Testing | 45 min |

---

## New Dependencies Added

```
@radix-ui/react-checkbox
@radix-ui/react-dialog (used by Sheet)
@radix-ui/react-popover
@radix-ui/react-separator
@radix-ui/react-slot
class-variance-authority
clsx
tailwind-merge
@fontsource/jetbrains-mono
```

These are installed automatically by `npx shadcn@latest add ...` (except the font).
