# VS Code Extension — Responsive WebView UI

## Problem

WebView 패널이 좁은 폭(사이드바 옆, 분할 에디터)에서 열릴 때 레이아웃이 깨진다.
고정 그리드 컬럼, 하드코딩된 min-height/min-width, 미디어 쿼리 부족이 원인.

## Scope

CSS 반응형 레이아웃 수정만 수행. 부분 DOM 업데이트, 기능 추가 등은 범위 밖.

## Changes

### 1. styles.ts — 그리드 레이아웃

| 셀렉터 | Before | After |
|---------|--------|-------|
| `.grid-2` | `repeat(2, minmax(0, 1fr))` | `repeat(auto-fit, minmax(240px, 1fr))` |
| `.grid-3` | `repeat(3, minmax(0, 1fr))` | `repeat(auto-fit, minmax(240px, 1fr))` |
| `.grid-sidebar` | `280px minmax(0, 1fr)` | `minmax(240px, 280px) minmax(0, 1fr)` (비대칭 유지, 600px 이하에서 1fr로 붕괴) |
| `.summary-grid` | `repeat(3, minmax(0, 1fr))` | `repeat(auto-fit, minmax(120px, 1fr))` |
| `.kv-grid` | `repeat(2, minmax(0, 1fr))` | `repeat(auto-fit, minmax(200px, 1fr))` |

### 2. styles.ts — 하드코딩 제거

- `.dashboard-card { min-height: 340px }` → 삭제
- `.dashboard-grid { align-content: stretch }` + `grid-auto-rows: 1fr` → 삭제 (자연 높이 사용)

### 3. styles.ts — 미디어 쿼리 보강

```css
@media (max-width: 600px) {
  body { padding: 16px; }
  .grid-2, .grid-3, .grid-sidebar, .summary-grid, .kv-grid {
    grid-template-columns: 1fr;
  }
  .flex-between { flex-direction: column; align-items: flex-start; }
}
```

기존 960px 쿼리는 유지하되, 600px 이하에서 강제 1컬럼 + 수직 스택 적용.

### 4. 패널 인라인 스타일 제거

| 파일 | 인라인 스타일 | 대체 |
|------|-------------|------|
| `prompt-diff-panel.ts` | `style="min-width:220px"` | `.select-wrap` 클래스 사용 |
| `snapshot-diff-panel.ts` | `style="min-width:220px"` | `.select-wrap` 클래스 사용 |
| `history-panel.ts` | `style="min-width:260px; flex:1"` | `.select-wrap` 클래스 사용 |
| `prompt-form-panel.ts` | `style="grid-column: 1 / -1"` (3곳: line 258, 262, 290) | `.full-width` 클래스 사용 |

새 유틸리티 클래스:
```css
.select-wrap { flex: 1; min-width: 0; }
.full-width { grid-column: 1 / -1; }
```

### 5. 테이블 오버플로우

```css
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { min-width: 480px; }
```

좁은 화면에서 테이블이 가로 스크롤 가능하도록 래퍼 추가.
`components.ts`의 `table()`과 `clickableTable()` 반환값을 `<div class="table-wrap">...</div>`로 감싸기.

### 6. snapshot-diff-panel.ts — 인라인 컬러 스타일

lines 51-53의 `style="color:#16a34a"` 등 인라인 컬러를 CSS 변수로 교체:
```html
<!-- Before -->
<div class="count" style="color:#16a34a">

<!-- After -->
<div class="count" style="color:var(--green)">
```

## Files to modify

1. `vscode-extension/src/templates/styles.ts` — 모든 CSS 변경
2. `vscode-extension/src/templates/components.ts` — `table()`, `clickableTable()`에 `.table-wrap` 래퍼 추가
3. `vscode-extension/src/panels/prompt-diff-panel.ts` — 인라인 스타일 → 클래스
4. `vscode-extension/src/panels/snapshot-diff-panel.ts` — 인라인 스타일 → 클래스
5. `vscode-extension/src/panels/history-panel.ts` — 인라인 스타일 → 클래스
6. `vscode-extension/src/panels/prompt-form-panel.ts` — 인라인 스타일 → 클래스
7. `vscode-extension/src/panels/dashboard-panel.ts` — `dashboard-grid`에 `grid-3` 클래스 추가 (현재 컬럼 정의 없음), 관련 클래스 정리
8. `vscode-extension/src/panels/snapshot-diff-panel.ts` — 인라인 컬러 → CSS 변수

## Not in scope

- 부분 DOM 업데이트 (전체 HTML 교체 방식 유지)
- 새로운 기능 추가
- 컬러/테마 변경
- 프레임워크 도입
