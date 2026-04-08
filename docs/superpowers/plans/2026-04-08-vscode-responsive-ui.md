# VS Code Extension Responsive UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix WebView layout breakage at narrow panel widths by making CSS grids responsive and removing hardcoded sizes.

**Architecture:** CSS-only changes in `styles.ts` + inline style cleanup in panel files + table overflow wrapper in `components.ts`. No logic changes, no new dependencies.

**Tech Stack:** TypeScript (VS Code extension), CSS Grid, CSS custom properties

**Spec:** `docs/superpowers/specs/2026-04-08-vscode-responsive-ui-design.md`

---

### Task 1: Responsive grids and hardcoded size removal in styles.ts

**Files:**
- Modify: `vscode-extension/src/templates/styles.ts`

- [ ] **Step 1: Change `.grid-2` to auto-fit**

```typescript
// In getStyles(), find:
.grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
// Replace with:
.grid-2 { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
```

- [ ] **Step 2: Change `.grid-3` to auto-fit**

```typescript
// Find:
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
// Replace with:
.grid-3 { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
```

- [ ] **Step 3: Change `.grid-sidebar` to flexible asymmetric**

```typescript
// Find:
.grid-sidebar { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 20px; }
// Replace with:
.grid-sidebar { display: grid; grid-template-columns: minmax(240px, 280px) minmax(0, 1fr); gap: 20px; }
```

- [ ] **Step 4: Change `.summary-grid` to auto-fit**

```typescript
// Find:
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
// Replace with:
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; }
```

- [ ] **Step 5: Change `.kv-grid` to auto-fit**

```typescript
// Find:
.kv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
// Replace with:
.kv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
```

- [ ] **Step 6: Remove dashboard card hardcoded heights**

```typescript
// Find and delete this entire block:
.dashboard-grid { align-items: stretch; grid-auto-rows: 1fr; align-content: stretch; }

// Find this combined rule:
.dashboard-grid > .card,
.dashboard-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 340px;
}
// Replace with (remove min-height only, keep rest intact):
.dashboard-grid > .card,
.dashboard-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
```

- [ ] **Step 7: Add utility classes**

Add after `.hidden { display: none !important; }`:

```css
.select-wrap { flex: 1; min-width: 0; }
.full-width { grid-column: 1 / -1; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
```

- [ ] **Step 8: Add table min-width**

```typescript
// Find:
table { width: 100%; border-collapse: collapse; font-size: 13px; }
// Replace with:
table { width: 100%; min-width: 480px; border-collapse: collapse; font-size: 13px; }
```

- [ ] **Step 9: Add 600px media query**

Add **after** the existing `@media (max-width: 960px)` block (so 600px rules override 960px where needed):

```css
@media (max-width: 600px) {
  .flex-between { flex-direction: column; align-items: flex-start; }
}
```

Note: The 960px query already handles `body { padding: 16px }` and grid 1-column fallback. The 600px query only adds `.flex-between` vertical stacking for very narrow panels.

- [ ] **Step 10: Build to verify no syntax errors**

Run: `cd vscode-extension && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 11: Commit**

```bash
git add vscode-extension/src/templates/styles.ts
git commit -m "fix(vscode): make CSS grids responsive and remove hardcoded sizes"
```

---

### Task 2: Table overflow wrapper in components.ts

**Files:**
- Modify: `vscode-extension/src/templates/components.ts`

- [ ] **Step 1: Wrap `table()` return value**

```typescript
// Find in table():
return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
// Replace with:
return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
```

- [ ] **Step 2: Wrap `clickableTable()` return value**

```typescript
// Find in clickableTable():
return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
// Replace with:
return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
```

- [ ] **Step 3: Build to verify**

Run: `cd vscode-extension && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add vscode-extension/src/templates/components.ts
git commit -m "fix(vscode): add table overflow wrapper for narrow panels"
```

---

### Task 3: Remove inline styles from panel files

**Files:**
- Modify: `vscode-extension/src/panels/prompt-diff-panel.ts`
- Modify: `vscode-extension/src/panels/snapshot-diff-panel.ts`
- Modify: `vscode-extension/src/panels/history-panel.ts`
- Modify: `vscode-extension/src/panels/prompt-form-panel.ts`
- Modify: `vscode-extension/src/panels/dashboard-panel.ts`

- [ ] **Step 1: prompt-diff-panel.ts — replace inline min-width**

```typescript
// Find (two occurrences):
<div style="min-width:220px">${select(
// Replace both with:
<div class="select-wrap">${select(
```

- [ ] **Step 2: snapshot-diff-panel.ts — replace inline min-width**

```typescript
// Find (two occurrences):
<div style="min-width:220px">${select(
// Replace both with:
<div class="select-wrap">${select(
```

- [ ] **Step 3: snapshot-diff-panel.ts — replace inline colors with CSS variables**

```typescript
// Find:
<div class="count" style="color:#16a34a">${diff.added_ids.length}</div>
// Replace with:
<div class="count" style="color:var(--green)">${diff.added_ids.length}</div>

// Find:
<div class="count" style="color:#dc2626">${diff.removed_ids.length}</div>
// Replace with:
<div class="count" style="color:var(--red)">${diff.removed_ids.length}</div>

// Find:
<div class="count" style="color:#ca8a04">${diff.changed_ids.length}</div>
// Replace with:
<div class="count" style="color:var(--yellow)">${diff.changed_ids.length}</div>
```

- [ ] **Step 4: history-panel.ts — replace inline min-width**

```typescript
// Find:
<div style="min-width:260px; flex:1">
// Replace with:
<div class="select-wrap">
```

- [ ] **Step 5: prompt-form-panel.ts — replace inline grid-column (3 occurrences)**

```typescript
// Find all three:
<div style="grid-column: 1 / -1">
// Replace all with:
<div class="full-width">
```

- [ ] **Step 6: dashboard-panel.ts — add grid-3 class to dashboard grid**

```typescript
// Find:
<div class="grid dashboard-grid">
// Replace with:
<div class="grid grid-3 dashboard-grid">
```

- [ ] **Step 7: Build to verify**

Run: `cd vscode-extension && npm run build`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add vscode-extension/src/panels/
git commit -m "fix(vscode): replace inline styles with responsive CSS classes"
```
