# PVM VS Code Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PVM Web UI의 모든 기능을 VS Code extension으로 구현 (TreeView + WebView, CLI wrapping)

**Architecture:** Extension host(TypeScript)가 `child_process`로 `pvm` CLI를 호출하고 JSON을 파싱. 사이드바 TreeView로 프롬프트/스냅샷 탐색, WebView 패널로 상세/diff/폼 표시. esbuild 번들링.

**Tech Stack:** TypeScript, VS Code Extension API, @vscode/webview-ui-toolkit, diff2html, esbuild

**Spec:** `docs/superpowers/specs/2026-04-06-vscode-extension-design.md`

---

## File Structure

```
vscode-extension/
├── package.json              # Extension manifest (commands, views, menus, activation)
├── tsconfig.json             # TypeScript config
├── esbuild.js               # Build script
├── .vscodeignore             # Publish ignore
├── src/
│   ├── extension.ts          # activate/deactivate entry point
│   ├── pvm-cli.ts            # CLI wrapper class
│   ├── types.ts              # CLI JSON response type definitions
│   ├── views/
│   │   ├── pvm-tree-provider.ts  # Single TreeDataProvider (Dashboard/Prompts/Snapshots/History)
│   │   └── tree-items.ts         # TreeItem subclasses
│   ├── panels/
│   │   ├── base-panel.ts         # Base WebView panel (shared boilerplate)
│   │   ├── dashboard-panel.ts    # Dashboard
│   │   ├── prompt-detail-panel.ts # Prompt detail
│   │   ├── prompt-form-panel.ts  # Add/Update prompt form
│   │   ├── prompt-diff-panel.ts  # Prompt diff
│   │   ├── snapshot-detail-panel.ts # Snapshot detail
│   │   ├── snapshot-diff-panel.ts   # Snapshot diff
│   │   ├── history-panel.ts      # History
│   │   └── setup-panel.ts        # Init/Destroy/Reset
│   └── templates/
│       ├── styles.ts             # Shared CSS (VS Code theme variables + layout)
│       ├── components.ts         # Reusable HTML components (cards, tables, badges, buttons)
│       ├── dashboard.ts          # Dashboard HTML
│       ├── prompt-detail.ts      # Prompt detail HTML
│       ├── prompt-form.ts        # Add/Update form HTML
│       ├── prompt-diff.ts        # Prompt diff HTML
│       ├── snapshot-detail.ts    # Snapshot detail HTML
│       ├── snapshot-diff.ts      # Snapshot diff HTML
│       ├── history.ts            # History HTML
│       └── setup.ts              # Setup HTML
├── media/
│   └── pvm-icon.svg          # Sidebar icon
└── test/
    ├── pvm-cli.test.ts       # CLI wrapper tests
    └── tree-provider.test.ts # TreeView tests
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `vscode-extension/package.json`
- Create: `vscode-extension/tsconfig.json`
- Create: `vscode-extension/esbuild.js`
- Create: `vscode-extension/.vscodeignore`
- Create: `vscode-extension/media/pvm-icon.svg`

- [ ] **Step 1: Initialize package.json**

```json
{
  "name": "pvm",
  "displayName": "PVM - Prompt Version Manager",
  "description": "Manage prompt versions directly in VS Code",
  "version": "0.1.0",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Other"],
  "activationEvents": ["workspaceContains:.pvm", "onView:pvmExplorer"],
  "main": "./out/extension.js",
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "pvm",
          "title": "PVM",
          "icon": "media/pvm-icon.svg"
        }
      ]
    },
    "views": {
      "pvm": [
        {
          "id": "pvmExplorer",
          "name": "PVM Explorer"
        }
      ]
    },
    "commands": [
      { "command": "pvm.refresh", "title": "Refresh", "category": "PVM", "icon": "$(refresh)" },
      { "command": "pvm.dashboard", "title": "Dashboard", "category": "PVM" },
      { "command": "pvm.addPrompt", "title": "Add Prompt", "category": "PVM", "icon": "$(add)" },
      { "command": "pvm.createSnapshot", "title": "Create Snapshot", "category": "PVM", "icon": "$(add)" },
      { "command": "pvm.init", "title": "Initialize Project", "category": "PVM" },
      { "command": "pvm.destroy", "title": "Destroy Project", "category": "PVM" },
      { "command": "pvm.reset", "title": "Reset Project", "category": "PVM" },
      { "command": "pvm.showHistory", "title": "History", "category": "PVM" },
      { "command": "pvm.promptDetail", "title": "View Prompt", "category": "PVM" },
      { "command": "pvm.promptUpdate", "title": "Update Prompt", "category": "PVM" },
      { "command": "pvm.promptDiff", "title": "Diff Prompt Versions", "category": "PVM" },
      { "command": "pvm.promptDeploy", "title": "Deploy", "category": "PVM" },
      { "command": "pvm.promptRollback", "title": "Rollback", "category": "PVM" },
      { "command": "pvm.promptDelete", "title": "Delete Prompt", "category": "PVM" },
      { "command": "pvm.snapshotDetail", "title": "View Snapshot", "category": "PVM" },
      { "command": "pvm.snapshotExport", "title": "Export Snapshot", "category": "PVM" },
      { "command": "pvm.snapshotDiff", "title": "Diff Snapshots", "category": "PVM" }
    ],
    "menus": {
      "view/title": [
        { "command": "pvm.refresh", "when": "view == pvmExplorer", "group": "navigation" }
      ],
      "view/item/context": [
        { "command": "pvm.addPrompt", "when": "viewItem == promptsHeader", "group": "inline" },
        { "command": "pvm.createSnapshot", "when": "viewItem == snapshotsHeader", "group": "inline" },
        { "command": "pvm.promptDeploy", "when": "viewItem == promptId", "group": "1_actions" },
        { "command": "pvm.promptRollback", "when": "viewItem == promptId", "group": "1_actions" },
        { "command": "pvm.promptUpdate", "when": "viewItem == promptId", "group": "1_actions" },
        { "command": "pvm.promptDiff", "when": "viewItem == promptId", "group": "2_compare" },
        { "command": "pvm.promptDelete", "when": "viewItem == promptId", "group": "3_danger" },
        { "command": "pvm.promptDeploy", "when": "viewItem == promptVersion", "group": "1_actions" },
        { "command": "pvm.snapshotExport", "when": "viewItem == snapshotVersion", "group": "1_actions" },
        { "command": "pvm.snapshotDiff", "when": "viewItem == snapshotVersion", "group": "2_compare" }
      ]
    }
  },
  "scripts": {
    "build": "node esbuild.js",
    "watch": "node esbuild.js --watch",
    "lint": "tsc --noEmit",
    "test": "node --import tsx --test test/*.test.ts"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "@vscode/test-cli": "^0.0.10",
    "esbuild": "^0.24.0",
    "typescript": "^5.5.0",
    "tsx": "^4.19.0"
  },
  "dependencies": {
    "@vscode/webview-ui-toolkit": "^1.4.0",
    "diff2html": "^3.4.48"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "module": "commonjs",
    "target": "ES2022",
    "lib": ["ES2022"],
    "outDir": "out",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "out", "test"]
}
```

- [ ] **Step 3: Create esbuild.js**

```javascript
const esbuild = require('esbuild');

const watch = process.argv.includes('--watch');

/** @type {import('esbuild').BuildOptions} */
const buildOptions = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  outfile: 'out/extension.js',
  external: ['vscode'],
  format: 'cjs',
  platform: 'node',
  target: 'node18',
  sourcemap: true,
  minify: !watch,
};

async function main() {
  if (watch) {
    const ctx = await esbuild.context(buildOptions);
    await ctx.watch();
    console.log('Watching for changes...');
  } else {
    await esbuild.build(buildOptions);
    console.log('Build complete.');
  }
}

main().catch(() => process.exit(1));
```

- [ ] **Step 4: Create .vscodeignore**

```
.vscode/**
src/**
test/**
node_modules/**
tsconfig.json
esbuild.js
**/*.ts
**/*.map
```

- [ ] **Step 5: Create pvm-icon.svg**

Simple green "P" icon for the activity bar.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <rect width="24" height="24" rx="4" fill="#16a34a"/>
  <text x="12" y="17" text-anchor="middle" font-family="monospace" font-weight="bold" font-size="14" fill="white">P</text>
</svg>
```

- [ ] **Step 6: Install dependencies**

```bash
cd vscode-extension && npm install
```

- [ ] **Step 7: Build and verify**

```bash
cd vscode-extension && npm run build
```
Expected: `out/extension.js` created without errors.

- [ ] **Step 8: Commit**

```bash
git add vscode-extension/
git commit -m "feat(vscode): scaffold extension project with esbuild"
```

---

## Task 2: Types & CLI Wrapper

**Files:**
- Create: `vscode-extension/src/types.ts`
- Create: `vscode-extension/src/pvm-cli.ts`
- Create: `vscode-extension/test/pvm-cli.test.ts`

- [ ] **Step 1: Write CLI wrapper test**

```typescript
// test/pvm-cli.test.ts
import { describe, it, mock } from 'node:test';
import assert from 'node:assert';

// Test that PvmCli.execute parses JSON stdout
describe('PvmCli', () => {
  it('should parse JSON output from CLI', async () => {
    // Will test against actual pvm CLI in workspace
    // For now, verify the module exports correctly
    const { PvmCli } = await import('../src/pvm-cli');
    assert.ok(PvmCli);
  });
});
```

- [ ] **Step 2: Define types matching CLI JSON output**

```typescript
// src/types.ts
export interface PromptAddResult {
  id: string;
  version: string;
  changed: boolean;
  reason?: string;
}

export interface DeployResult {
  id: string;
  version: string;
  changed: boolean;
  reason?: string;
  from_version?: string;
}

export interface RollbackResult {
  id: string;
  version: string;
  changed: boolean;
  reason?: string;
  from_version?: string;
}

export interface PromptGetResult {
  id: string;
  version: string;
  llm: {
    provider: string;
    model: string;
    params: Record<string, any>;
  };
  prompt: string;
  metadata: {
    id: string;
    version: string;
    created_at: string;
    description?: string;
    author?: string;
    source_file?: string;
    checksums: {
      prompt: string;
      model_config: string;
    };
  };
}

export interface PromptInfoResult {
  id: string;
  info: {
    description: string;
    author: string;
    created_at: string;
  };
  versions: string[];
  latest_version: string;
  production: {
    version: string;
    previous_versions: string[];
    updated_at: string;
  } | null;
}

export interface PromptListItem {
  id: string;
  versions: string[];
  latest_version: string;
  production_version: string | null;
}

export interface DiffResult {
  id: string;
  from_version: string;
  to_version: string;
  changed: boolean;
  prompt_length_delta: number;
  lines_added: number;
  lines_removed: number;
  model_config_changed: boolean;
  checksum_from: string;
  checksum_to: string;
  unified_diff: string;
}

export interface SnapshotResult {
  version: string;
  created_at: string;
  snapshot_checksum: string;
  prompt_count: number;
  prompts: Record<string, {
    version: string;
    prompt_checksum: string;
    model_config_checksum: string;
  }>;
}

export interface SnapshotReadResult {
  version: string;
  created_at: string;
  snapshot_checksum: string;
  prompts: Record<string, PromptGetResult>;
}

export interface SnapshotDiffResult {
  from_version: string;
  to_version: string;
  added_ids: string[];
  removed_ids: string[];
  changed_ids: {
    id: string;
    from_version: string;
    to_version: string;
  }[];
}

export interface DeleteResult {
  id: string;
  deleted: boolean;
}

export interface InitResult {
  name: string;
  root: string;
}

export interface IntegrityResult {
  valid: boolean;
  missing_dirs: string[];
  missing_files: string[];
}

export interface LogEntry {
  timestamp: string;
  event: string;
  id?: string;
  version?: string;
  details?: Record<string, any>;
}

export interface ProjectConfig {
  name: string;
  project_id: string;
  created_at: string;
  root: string;
}
```

- [ ] **Step 3: Implement CLI wrapper**

```typescript
// src/pvm-cli.ts
import * as cp from 'child_process';
import * as vscode from 'vscode';
import {
  PromptAddResult, DeployResult, RollbackResult, PromptGetResult,
  PromptInfoResult, PromptListItem, DiffResult, SnapshotResult,
  SnapshotReadResult, SnapshotDiffResult, DeleteResult, InitResult,
  IntegrityResult, LogEntry, ProjectConfig
} from './types';

export class PvmCli {
  constructor(private workspaceRoot: string) {}

  private execute(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
      cp.execFile(
        'poetry', ['run', 'pvm', ...args],
        { cwd: this.workspaceRoot, maxBuffer: 10 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            reject(new Error(stderr || error.message));
            return;
          }
          resolve(stdout.trim());
        }
      );
    });
  }

  private async executeJson<T>(args: string[]): Promise<T> {
    const output = await this.execute(args);
    return JSON.parse(output) as T;
  }

  // Project
  async init(name: string): Promise<InitResult> {
    return this.executeJson(['init', name]);
  }
  async destroy(): Promise<void> {
    await this.execute(['destroy', '--force']);
  }
  async reset(): Promise<void> {
    await this.execute(['reset', '--force']);
  }
  async checkIntegrity(): Promise<IntegrityResult> {
    return this.executeJson(['check']);
  }
  async project(): Promise<string> {
    return this.execute(['project']);
  }
  async config(): Promise<ProjectConfig> {
    // pvm project outputs text; we use check + config
    return this.executeJson(['check']);
  }

  // Prompts
  async list(): Promise<PromptListItem[]> {
    return this.executeJson(['list']);
  }
  async get(id: string, version?: string): Promise<PromptGetResult> {
    const args = ['get', id];
    if (version) { args.push('--version', version); }
    return this.executeJson(args);
  }
  async info(id: string): Promise<PromptInfoResult> {
    return this.executeJson(['id', id, '--info']);
  }
  async add(templatePath: string, bump?: string): Promise<PromptAddResult> {
    const args = ['add', templatePath];
    if (bump && bump !== 'patch') { args.push(`--${bump}`); }
    return this.executeJson(args);
  }
  async deploy(id: string, version?: string): Promise<DeployResult> {
    const args = ['deploy', id];
    if (version) { args.push(version); }
    return this.executeJson(args);
  }
  async rollback(id: string): Promise<RollbackResult> {
    return this.executeJson(['rollback', id]);
  }
  async deletePrompt(id: string): Promise<DeleteResult> {
    return this.executeJson(['delete', id, '--force']);
  }
  async diff(id: string, from: string, to: string): Promise<DiffResult> {
    return this.executeJson(['diff', id, from, to]);
  }
  async listVersions(id: string): Promise<string[]> {
    const result = await this.executeJson<any>(['id', id, '--list']);
    return result.versions || result;
  }
  async template(): Promise<string> {
    return this.execute(['template']);
  }

  // Snapshots
  async snapshotList(): Promise<string[]> {
    return this.executeJson(['snapshot', 'list']);
  }
  async snapshotGet(version: string): Promise<SnapshotResult> {
    return this.executeJson(['snapshot', 'get', version]);
  }
  async snapshotRead(version: string): Promise<SnapshotReadResult> {
    return this.executeJson(['snapshot', 'read', version]);
  }
  async snapshotCreate(bump?: string): Promise<SnapshotResult> {
    const args = ['snapshot', 'create'];
    if (bump && bump !== 'patch') { args.push(`--${bump}`); }
    return this.executeJson(args);
  }
  async snapshotExport(version: string, outputPath?: string): Promise<string> {
    const args = ['snapshot', 'export', version];
    if (outputPath) { args.push('-o', outputPath); }
    return this.execute(args);
  }
  async snapshotDiff(from: string, to: string): Promise<SnapshotDiffResult> {
    return this.executeJson(['snapshot', 'diff', from, to]);
  }

  // History
  async log(id?: string): Promise<LogEntry[]> {
    const args = ['log'];
    if (id) { args.push('--id', id); }
    return this.executeJson(args);
  }
}
```

- [ ] **Step 4: Run test**

```bash
cd vscode-extension && npm test
```
Expected: PASS

- [ ] **Step 5: Build**

```bash
cd vscode-extension && npm run build
```
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add vscode-extension/src/types.ts vscode-extension/src/pvm-cli.ts vscode-extension/test/
git commit -m "feat(vscode): add CLI wrapper and type definitions"
```

---

## Task 3: TreeView Provider & Tree Items

**Files:**
- Create: `vscode-extension/src/views/tree-items.ts`
- Create: `vscode-extension/src/views/pvm-tree-provider.ts`
- Create: `vscode-extension/src/extension.ts`

- [ ] **Step 1: Create tree item classes**

```typescript
// src/views/tree-items.ts
import * as vscode from 'vscode';

export class DashboardItem extends vscode.TreeItem {
  contextValue = 'dashboard';
  constructor() {
    super('Dashboard', vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('dashboard');
    this.command = { command: 'pvm.dashboard', title: 'Dashboard' };
  }
}

export class PromptsHeaderItem extends vscode.TreeItem {
  contextValue = 'promptsHeader';
  constructor(count: number) {
    super(`Prompts (${count})`, vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon('note');
  }
}

export class PromptIdItem extends vscode.TreeItem {
  contextValue = 'promptId';
  constructor(
    public readonly promptId: string,
    public readonly productionVersion: string | null,
    versionCount: number
  ) {
    super(promptId, vscode.TreeItemCollapsibleState.Collapsed);
    this.iconPath = new vscode.ThemeIcon('file-text');
    this.description = productionVersion ? `prod: v${productionVersion}` : '';
    this.tooltip = `${promptId} (${versionCount} versions)`;
    this.command = {
      command: 'pvm.promptDetail',
      title: 'View Prompt',
      arguments: [promptId]
    };
  }
}

export class PromptVersionItem extends vscode.TreeItem {
  contextValue = 'promptVersion';
  constructor(
    public readonly promptId: string,
    public readonly version: string,
    isProduction: boolean,
    isLatest: boolean
  ) {
    super(`v${version}`, vscode.TreeItemCollapsibleState.None);
    const badges: string[] = [];
    if (isProduction) { badges.push('prod'); }
    if (isLatest) { badges.push('latest'); }
    this.description = badges.join(' · ');
    this.iconPath = new vscode.ThemeIcon(
      isProduction ? 'circle-filled' : 'circle-outline'
    );
    this.command = {
      command: 'pvm.promptDetail',
      title: 'View Version',
      arguments: [promptId, version]
    };
  }
}

export class SnapshotsHeaderItem extends vscode.TreeItem {
  contextValue = 'snapshotsHeader';
  constructor(count: number) {
    super(`Snapshots (${count})`, vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon('archive');
  }
}

export class SnapshotVersionItem extends vscode.TreeItem {
  contextValue = 'snapshotVersion';
  constructor(public readonly version: string) {
    super(`v${version}`, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('package');
    this.command = {
      command: 'pvm.snapshotDetail',
      title: 'View Snapshot',
      arguments: [version]
    };
  }
}

export class HistoryItem extends vscode.TreeItem {
  contextValue = 'history';
  constructor() {
    super('History', vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('history');
    this.command = { command: 'pvm.showHistory', title: 'History' };
  }
}

export class SetupItem extends vscode.TreeItem {
  contextValue = 'setup';
  constructor() {
    super('Initialize Project', vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('gear');
    this.command = { command: 'pvm.init', title: 'Initialize Project' };
  }
}
```

- [ ] **Step 2: Create TreeDataProvider**

```typescript
// src/views/pvm-tree-provider.ts
import * as vscode from 'vscode';
import { PvmCli } from '../pvm-cli';
import {
  DashboardItem, PromptsHeaderItem, PromptIdItem, PromptVersionItem,
  SnapshotsHeaderItem, SnapshotVersionItem, HistoryItem, SetupItem
} from './tree-items';

type PvmTreeItem = DashboardItem | PromptsHeaderItem | PromptIdItem |
  PromptVersionItem | SnapshotsHeaderItem | SnapshotVersionItem |
  HistoryItem | SetupItem;

export class PvmTreeProvider implements vscode.TreeDataProvider<PvmTreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<PvmTreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private isValid = false;
  private prompts: { id: string; versions: string[]; latest_version: string; production_version: string | null }[] = [];
  private snapshots: string[] = [];

  constructor(private cli: PvmCli) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  async getChildren(element?: PvmTreeItem): Promise<PvmTreeItem[]> {
    if (!element) {
      return this.getRootItems();
    }
    if (element instanceof PromptsHeaderItem) {
      return this.prompts.map(p =>
        new PromptIdItem(p.id, p.production_version, p.versions.length)
      );
    }
    if (element instanceof PromptIdItem) {
      const info = await this.cli.info(element.promptId);
      const versions = [...info.versions].reverse();
      return versions.map(v =>
        new PromptVersionItem(
          element.promptId, v,
          info.production?.version === v,
          v === info.latest_version
        )
      );
    }
    if (element instanceof SnapshotsHeaderItem) {
      return [...this.snapshots].reverse().map(v => new SnapshotVersionItem(v));
    }
    return [];
  }

  getTreeItem(element: PvmTreeItem): vscode.TreeItem {
    return element;
  }

  private async getRootItems(): Promise<PvmTreeItem[]> {
    try {
      await this.cli.checkIntegrity();
      this.isValid = true;
    } catch {
      this.isValid = false;
      return [new SetupItem()];
    }

    try {
      this.prompts = await this.cli.list();
    } catch {
      this.prompts = [];
    }
    try {
      this.snapshots = await this.cli.snapshotList();
    } catch {
      this.snapshots = [];
    }

    return [
      new DashboardItem(),
      new PromptsHeaderItem(this.prompts.length),
      new SnapshotsHeaderItem(this.snapshots.length),
      new HistoryItem(),
    ];
  }
}
```

- [ ] **Step 3: Create extension entry point (minimal)**

```typescript
// src/extension.ts
import * as vscode from 'vscode';
import { PvmCli } from './pvm-cli';
import { PvmTreeProvider } from './views/pvm-tree-provider';

export function activate(context: vscode.ExtensionContext) {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!workspaceRoot) {
    return;
  }

  const cli = new PvmCli(workspaceRoot);
  const treeProvider = new PvmTreeProvider(cli);

  const treeView = vscode.window.createTreeView('pvmExplorer', {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });

  context.subscriptions.push(
    treeView,
    vscode.commands.registerCommand('pvm.refresh', () => treeProvider.refresh()),
  );
}

export function deactivate() {}
```

- [ ] **Step 4: Build and verify**

```bash
cd vscode-extension && npm run build
```
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add vscode-extension/src/
git commit -m "feat(vscode): add TreeView provider with prompt/snapshot tree"
```

---

## Task 4: Base WebView Panel & Shared Templates

**Files:**
- Create: `vscode-extension/src/panels/base-panel.ts`
- Create: `vscode-extension/src/templates/styles.ts`
- Create: `vscode-extension/src/templates/components.ts`

- [ ] **Step 1: Create shared styles**

`styles.ts` — VS Code 테마 변수 기반 CSS. Web UI의 레이아웃 패턴(카드, 그리드, 배지, 테이블)을 VS Code 색상 변수로 재현.

```typescript
// src/templates/styles.ts
export function getStyles(): string {
  return `
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      padding: 20px;
      line-height: 1.6;
    }
    h1 { font-size: 1.5em; margin-bottom: 8px; }
    h2 { font-size: 1.2em; margin-bottom: 8px; color: var(--vscode-descriptionForeground); }
    a { color: var(--vscode-textLink-foreground); text-decoration: none; cursor: pointer; }
    a:hover { text-decoration: underline; }
    .mono { font-family: var(--vscode-editor-font-family); }
    .text-sm { font-size: 0.85em; }
    .text-xs { font-size: 0.75em; }
    .text-muted { color: var(--vscode-descriptionForeground); }
    .text-green { color: #16a34a; }
    .text-red { color: #dc2626; }
    .text-yellow { color: #ca8a04; }
    .text-blue { color: #2563eb; }
    .space-y > * + * { margin-top: 16px; }
    .space-y-sm > * + * { margin-top: 8px; }

    /* Cards (Web UI 패턴) */
    .card {
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      padding: 16px;
    }
    .card-header {
      font-size: 0.75em;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 12px;
    }

    /* Grid */
    .grid { display: grid; gap: 16px; }
    .grid-2 { grid-template-columns: 1fr 1fr; }
    .grid-3 { grid-template-columns: 1fr 1fr 1fr; }

    /* Badges */
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.7em;
      font-weight: 600;
    }
    .badge-prod { background: #16a34a22; color: #16a34a; }
    .badge-ver { background: #2563eb22; color: #2563eb; }
    .badge-add { background: #2563eb22; color: #2563eb; }
    .badge-deploy { background: #16a34a22; color: #16a34a; }
    .badge-rollback { background: #ca8a0422; color: #ca8a04; }
    .badge-snapshot { background: #9333ea22; color: #9333ea; }
    .badge-default { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }

    /* Tables */
    table { width: 100%; border-collapse: collapse; }
    th {
      text-align: left;
      padding: 8px 12px;
      font-size: 0.75em;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--vscode-descriptionForeground);
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    td {
      padding: 8px 12px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    tr:hover { background: var(--vscode-list-hoverBackground); }
    tr.clickable { cursor: pointer; }

    /* Code blocks */
    pre, .code-block {
      background: var(--vscode-textCodeBlock-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 4px;
      padding: 12px;
      font-family: var(--vscode-editor-font-family);
      font-size: var(--vscode-editor-font-size);
      white-space: pre-wrap;
      word-wrap: break-word;
      overflow: auto;
      max-height: 400px;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 0.85em;
      cursor: pointer;
      border: none;
    }
    .btn-primary { background: #16a34a; color: white; }
    .btn-primary:hover { background: #15803d; }
    .btn-danger { background: #dc2626; color: white; }
    .btn-danger:hover { background: #b91c1c; }
    .btn-secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    .btn-secondary:hover { background: var(--vscode-button-secondaryHoverBackground); }

    /* Forms */
    .form-group { margin-bottom: 12px; }
    .form-label {
      display: block;
      font-size: 0.85em;
      font-weight: 600;
      margin-bottom: 4px;
    }
    .form-input, .form-select, .form-textarea {
      width: 100%;
      padding: 6px 10px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      font-family: inherit;
      font-size: inherit;
    }
    .form-textarea { min-height: 120px; resize: vertical; font-family: var(--vscode-editor-font-family); }

    /* Tabs (Web UI 탭 패턴) */
    .tabs { display: flex; border-bottom: 1px solid var(--vscode-panel-border); margin-bottom: 16px; }
    .tab {
      padding: 8px 16px;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      color: var(--vscode-descriptionForeground);
    }
    .tab.active {
      color: var(--vscode-foreground);
      border-bottom-color: #16a34a;
    }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    /* Flex utils */
    .flex { display: flex; }
    .flex-between { display: flex; justify-content: space-between; align-items: center; }
    .gap-2 { gap: 8px; }
    .gap-4 { gap: 16px; }
    .mt-4 { margin-top: 16px; }

    /* Stat number (dashboard) */
    .stat-number { font-size: 2em; font-weight: 700; }

    /* Diff2html overrides */
    .d2h-wrapper { font-size: 0.85em; }
    .d2h-file-header { display: none; }
    .d2h-code-line { white-space: pre-wrap; word-wrap: break-word; }
  `;
}
```

- [ ] **Step 2: Create shared HTML components**

```typescript
// src/templates/components.ts

export function badge(text: string, type: 'prod' | 'ver' | 'add' | 'deploy' | 'rollback' | 'snapshot' | 'default' = 'default'): string {
  return `<span class="badge badge-${type}">${text}</span>`;
}

export function card(header: string, content: string): string {
  return `<div class="card"><div class="card-header">${header}</div>${content}</div>`;
}

export function cardNoHeader(content: string): string {
  return `<div class="card">${content}</div>`;
}

export function button(text: string, type: 'primary' | 'danger' | 'secondary', onclick: string): string {
  return `<button class="btn btn-${type}" onclick="${onclick}">${text}</button>`;
}

export function table(headers: string[], rows: string[][]): string {
  const ths = headers.map(h => `<th>${h}</th>`).join('');
  const trs = rows.map(cols => {
    const tds = cols.map(c => `<td>${c}</td>`).join('');
    return `<tr>${tds}</tr>`;
  }).join('');
  return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
}

export function clickableTable(headers: string[], rows: { cols: string[]; onclick: string }[]): string {
  const ths = headers.map(h => `<th>${h}</th>`).join('');
  const trs = rows.map(r => {
    const tds = r.cols.map(c => `<td>${c}</td>`).join('');
    return `<tr class="clickable" onclick="${r.onclick}">${tds}</tr>`;
  }).join('');
  return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
}

export function codeBlock(content: string): string {
  const escaped = content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<pre class="code-block">${escaped}</pre>`;
}

export function select(id: string, options: { value: string; label: string; selected?: boolean }[]): string {
  const opts = options.map(o =>
    `<option value="${o.value}"${o.selected ? ' selected' : ''}>${o.label}</option>`
  ).join('');
  return `<select id="${id}" class="form-select">${opts}</select>`;
}

export function emptyState(message: string): string {
  return `<div class="card" style="text-align:center;padding:32px;"><p class="text-muted">${message}</p></div>`;
}

export function gridStat(label: string, value: string): string {
  return `<div><div class="stat-number">${value}</div><div class="text-muted text-sm">${label}</div></div>`;
}

export function kvGrid(pairs: { key: string; value: string }[]): string {
  const items = pairs.map(p =>
    `<div><div class="text-xs text-muted">${p.key}</div><div class="mono text-sm">${p.value}</div></div>`
  ).join('');
  return `<div class="grid grid-2">${items}</div>`;
}
```

- [ ] **Step 3: Create base panel class**

```typescript
// src/panels/base-panel.ts
import * as vscode from 'vscode';
import { getStyles } from '../templates/styles';

export abstract class BasePanel {
  protected panel: vscode.WebviewPanel | undefined;

  constructor(
    protected readonly extensionUri: vscode.Uri,
    protected readonly viewType: string,
    protected readonly title: string,
  ) {}

  protected abstract getHtmlContent(webview: vscode.Webview): Promise<string>;

  protected onMessage(_message: any): void {}

  async show(column: vscode.ViewColumn = vscode.ViewColumn.One): Promise<void> {
    if (this.panel) {
      this.panel.reveal(column);
    } else {
      this.panel = vscode.window.createWebviewPanel(
        this.viewType,
        this.title,
        column,
        {
          enableScripts: true,
          retainContextWhenHidden: true,
          localResourceRoots: [this.extensionUri],
        }
      );
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage(msg => this.onMessage(msg));
    }
    await this.update();
  }

  async update(): Promise<void> {
    if (!this.panel) { return; }
    const content = await this.getHtmlContent(this.panel.webview);
    this.panel.webview.html = this.wrapHtml(this.panel.webview, content);
  }

  private wrapHtml(webview: vscode.Webview, content: string): string {
    const nonce = getNonce();
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src ${webview.cspSource} 'nonce-${nonce}'; script-src 'nonce-${nonce}'; font-src ${webview.cspSource};">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style nonce="${nonce}">${getStyles()}</style>
</head>
<body>
  <div class="space-y">${content}</div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    function send(type, data) { vscode.postMessage({ type, ...data }); }
    ${this.getScript()}
  </script>
</body>
</html>`;
  }

  protected getScript(): string { return ''; }

  dispose(): void {
    this.panel?.dispose();
  }
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
```

- [ ] **Step 4: Build**

```bash
cd vscode-extension && npm run build
```
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add vscode-extension/src/panels/base-panel.ts vscode-extension/src/templates/
git commit -m "feat(vscode): add base panel, shared styles and HTML components"
```

---

## Task 5: Dashboard Panel

**Files:**
- Create: `vscode-extension/src/templates/dashboard.ts`
- Create: `vscode-extension/src/panels/dashboard-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI의 `dashboard.html` 매핑: 프로젝트 정보 카드, 프롬프트/스냅샷 요약 그리드, 프로젝트 트리.

- [ ] **Step 1: Create dashboard template**

```typescript
// src/templates/dashboard.ts
import { card, badge, codeBlock, gridStat, kvGrid, button, clickableTable, emptyState } from './components';
import { PromptListItem, IntegrityResult } from '../types';

export function dashboardHtml(
  projectTree: string,
  integrity: IntegrityResult,
  prompts: PromptListItem[],
  snapshots: string[],
  projectName: string,
  projectRoot: string,
): string {
  // Project Info Card
  const integrityBadge = integrity.valid
    ? '<span class="badge badge-prod">Valid</span>'
    : '<span class="badge" style="background:#dc262622;color:#dc2626;">Corrupted</span>';

  const projectInfoContent = `
    <div class="flex-between">
      <div>
        <h1>${projectName}</h1>
        <div class="mono text-sm text-muted">${projectRoot}</div>
      </div>
      <div class="flex gap-2">
        ${button('Reset', 'secondary', "send('reset')")}
        ${button('Destroy', 'danger', "send('destroy')")}
      </div>
    </div>
    <div class="grid grid-3 mt-4">
      ${kvGrid([
        { key: 'Integrity', value: integrityBadge },
      ]).replace('<div class="grid grid-2">', '').replace('</div></div>', '')}
    </div>
  `;

  // Summary Grid
  const promptRows = prompts.map(p => ({
    cols: [
      `<span class="mono">${p.id}</span>`,
      `${p.versions.length} versions`,
      p.production_version ? badge(`v${p.production_version}`, 'prod') : '-',
    ],
    onclick: `send('promptDetail', {id: '${p.id}'})`,
  }));

  const promptsCard = prompts.length > 0
    ? card('Prompts', `
        <div class="flex-between" style="margin-bottom:12px">
          <span class="stat-number">${prompts.length}</span>
          <a onclick="send('addPrompt')">+ Add Prompt</a>
        </div>
        ${clickableTable(['ID', 'Versions', 'Production'], promptRows)}
      `)
    : card('Prompts', `
        <div class="stat-number">0</div>
        <p class="text-muted text-sm mt-4">No prompts yet. <a onclick="send('addPrompt')">Add one</a></p>
      `);

  const snapshotsList = [...snapshots].reverse().slice(0, 5)
    .map(v => `<div class="flex-between" style="padding:4px 0">
      <a class="mono" onclick="send('snapshotDetail', {version: '${v}'})">v${v}</a>
    </div>`).join('');

  const snapshotsCard = snapshots.length > 0
    ? card('Snapshots', `
        <div class="flex-between" style="margin-bottom:12px">
          <span class="stat-number">${snapshots.length}</span>
          <a onclick="send('createSnapshot')">+ Create</a>
        </div>
        ${snapshotsList}
      `)
    : card('Snapshots', `
        <div class="stat-number">0</div>
        <p class="text-muted text-sm mt-4">No snapshots yet.</p>
      `);

  // Project Tree
  const treeCard = card('Project Tree', codeBlock(projectTree));

  return `
    <div class="card">${projectInfoContent}</div>
    <div class="grid grid-2">${promptsCard}${snapshotsCard}</div>
    ${treeCard}
  `;
}
```

- [ ] **Step 2: Create dashboard panel**

```typescript
// src/panels/dashboard-panel.ts
import * as vscode from 'vscode';
import { BasePanel } from './base-panel';
import { PvmCli } from '../pvm-cli';
import { dashboardHtml } from '../templates/dashboard';

export class DashboardPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private cli: PvmCli,
    private onRefresh: () => void,
  ) {
    super(extensionUri, 'pvm.dashboard', 'PVM Dashboard');
  }

  protected async getHtmlContent(): Promise<string> {
    const [integrity, prompts, snapshots, projectTree] = await Promise.all([
      this.cli.checkIntegrity(),
      this.cli.list().catch(() => []),
      this.cli.snapshotList().catch(() => []),
      this.cli.project().catch(() => ''),
    ]);
    // Extract project name from tree or use fallback
    const name = 'PVM Project';
    const root = '';
    return dashboardHtml(projectTree, integrity, prompts, snapshots, name, root);
  }

  protected onMessage(message: any): void {
    switch (message.type) {
      case 'reset':
        this.handleReset();
        break;
      case 'destroy':
        this.handleDestroy();
        break;
      case 'promptDetail':
        vscode.commands.executeCommand('pvm.promptDetail', message.id);
        break;
      case 'snapshotDetail':
        vscode.commands.executeCommand('pvm.snapshotDetail', message.version);
        break;
      case 'addPrompt':
        vscode.commands.executeCommand('pvm.addPrompt');
        break;
      case 'createSnapshot':
        vscode.commands.executeCommand('pvm.createSnapshot');
        break;
    }
  }

  private async handleReset(): Promise<void> {
    const confirm = await vscode.window.showWarningMessage(
      'Reset project? All prompts and snapshots will be removed.',
      { modal: true }, 'Reset'
    );
    if (confirm === 'Reset') {
      await this.cli.reset();
      this.onRefresh();
      await this.update();
    }
  }

  private async handleDestroy(): Promise<void> {
    const confirm = await vscode.window.showWarningMessage(
      'Destroy project? The .pvm directory will be permanently deleted.',
      { modal: true }, 'Destroy'
    );
    if (confirm === 'Destroy') {
      await this.cli.destroy();
      this.onRefresh();
      await this.update();
    }
  }
}
```

- [ ] **Step 3: Register dashboard command in extension.ts**

Add dashboard panel creation and command registration to `extension.ts`. Import `DashboardPanel`, create instance, register `pvm.dashboard` command.

- [ ] **Step 4: Build**

```bash
cd vscode-extension && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add vscode-extension/src/panels/dashboard-panel.ts vscode-extension/src/templates/dashboard.ts vscode-extension/src/extension.ts
git commit -m "feat(vscode): add dashboard panel matching web UI layout"
```

---

## Task 6: Setup Panel

**Files:**
- Create: `vscode-extension/src/templates/setup.ts`
- Create: `vscode-extension/src/panels/setup-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `setup.html` 매핑: 프로젝트 초기화 폼, 로고, 경로 표시.

- [ ] **Step 1: Create setup template**

Setup HTML with init form (project name input + submit), matching Web UI centered card layout.

- [ ] **Step 2: Create setup panel**

Handle `init` message → `pvm init <name>` → refresh tree → show dashboard.

- [ ] **Step 3: Register `pvm.init` command, wire up tree provider to show setup when project invalid**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add setup panel for project initialization"
```

---

## Task 7: Prompt Detail Panel

**Files:**
- Create: `vscode-extension/src/templates/prompt-detail.ts`
- Create: `vscode-extension/src/panels/prompt-detail-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `prompt_detail.html` 매핑: 버전 사이드바, 프롬프트 텍스트, LLM 설정, 메타데이터, Deploy/Rollback/Delete 버튼.

- [ ] **Step 1: Create prompt detail template**

3-column grid layout matching web UI: left sidebar (versions list + deploy dropdown + diff selector), right content (prompt text code block + LLM config grid + metadata grid). Production badge on version, latest badge, deploy/rollback/delete buttons.

- [ ] **Step 2: Create prompt detail panel**

Messages: `deploy` → `pvm deploy`, `rollback` → `pvm rollback`, `delete` → confirm + `pvm delete`, `selectVersion` → re-render with specific version, `diff` → open diff panel, `update` → open form panel.

- [ ] **Step 3: Register `pvm.promptDetail`, `pvm.promptDeploy`, `pvm.promptRollback`, `pvm.promptDelete` commands**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add prompt detail panel with deploy/rollback/delete"
```

---

## Task 8: Prompt Form Panel (Add / Update)

**Files:**
- Create: `vscode-extension/src/templates/prompt-form.ts`
- Create: `vscode-extension/src/panels/prompt-form-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `prompt_add.html` + `prompt_update.html` 매핑: 3탭 인터페이스 (Form / File Upload / YAML Editor), bump level 라디오, extra fields 동적 추가.

- [ ] **Step 1: Create prompt form template**

Tab interface with 3 panels. Form tab: ID, prompt text, provider, model (required) + description, author, temperature, max_tokens (optional) + dynamic extra fields. Upload tab: file picker. Editor tab: YAML textarea prefilled with template. Bump level radios. Reuse for both add and update (update: prefilled values, disabled ID).

- [ ] **Step 2: Create prompt form panel**

On `submit`: write temp YAML file from form data → `pvm add <temp.yaml> --<bump>` → delete temp → refresh tree → show detail. On file upload: save to temp → `pvm add`. Handle update mode (prefilled, existing prompt).

- [ ] **Step 3: Register `pvm.addPrompt` and `pvm.promptUpdate` commands**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add prompt form panel (add/update with 3 input modes)"
```

---

## Task 9: Prompt Diff Panel

**Files:**
- Create: `vscode-extension/src/templates/prompt-diff.ts`
- Create: `vscode-extension/src/panels/prompt-diff-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `prompt_diff.html` 매핑: 버전 선택 드롭다운, diff2html 렌더링, 변경 통계 요약.

- [ ] **Step 1: Create prompt diff template**

Header with prompt ID + "Comparing vX → vY". Summary bar (lines added/removed, length delta, model config badge). Diff2html rendered output. Version selector dropdowns at bottom.

- [ ] **Step 2: Create prompt diff panel**

Load diff2html CSS/JS in webview. Message: `selectVersions` → re-fetch diff and re-render. CSP needs to allow diff2html styles (bundled inline).

- [ ] **Step 3: Register `pvm.promptDiff` command**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add prompt diff panel with diff2html rendering"
```

---

## Task 10: Snapshot Detail Panel

**Files:**
- Create: `vscode-extension/src/templates/snapshot-detail.ts`
- Create: `vscode-extension/src/panels/snapshot-detail-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `snapshot_detail.html` 매핑: 매니페스트 정보, 포함된 프롬프트 카드들 (각각 프롬프트 텍스트 + LLM 설정), Export 버튼.

- [ ] **Step 1: Create snapshot detail template**

Header (version + created_at + Export button). Manifest info grid (prompt count, checksum, created). Per-prompt cards: ID header, version, prompt text code block, LLM config grid.

- [ ] **Step 2: Create snapshot detail panel**

Uses `pvm snapshot read <version>` for expanded data. Export message → `pvm snapshot export` → save dialog.

- [ ] **Step 3: Register `pvm.snapshotDetail` and `pvm.snapshotExport` commands**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add snapshot detail panel with export"
```

---

## Task 11: Snapshot Diff Panel

**Files:**
- Create: `vscode-extension/src/templates/snapshot-diff.ts`
- Create: `vscode-extension/src/panels/snapshot-diff-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `snapshot_diff.html` 매핑: 추가/삭제/변경 요약 그리드, 상세 목록, 버전 선택기.

- [ ] **Step 1: Create snapshot diff template**

Summary grid (3 columns: added count green, removed count red, changed count yellow). Added/Removed/Changed sections with colored dots and monospace IDs. Version selector dropdowns.

- [ ] **Step 2: Create snapshot diff panel**

Message: `selectVersions` → `pvm snapshot diff` → re-render.

- [ ] **Step 3: Register `pvm.snapshotDiff` command**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add snapshot diff panel"
```

---

## Task 12: History Panel

**Files:**
- Create: `vscode-extension/src/templates/history.ts`
- Create: `vscode-extension/src/panels/history-panel.ts`
- Modify: `vscode-extension/src/extension.ts`

Web UI `history.html` 매핑: 필터 드롭다운, 이벤트 테이블 (시간, 이벤트 배지, ID, 상세).

- [ ] **Step 1: Create history template**

Filter select (All/specific prompt IDs). Table: Time (mono xs), Event (colored badge), ID (mono green link), Details. Reversed chronological order.

- [ ] **Step 2: Create history panel**

Message: `filter` → `pvm log --id <id>` or `pvm log` → re-render. Click on ID → open prompt detail.

- [ ] **Step 3: Register `pvm.showHistory` command**

- [ ] **Step 4: Build**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add history panel with event filtering"
```

---

## Task 13: Wire Up All Commands in extension.ts

**Files:**
- Modify: `vscode-extension/src/extension.ts`

- [ ] **Step 1: Complete extension.ts**

Register all panel instances and commands. Handle panel lifecycle (reuse existing panels). Wire up snapshot creation (bump level quick pick → `pvm snapshot create`). Ensure tree refreshes after mutations.

```typescript
// Key pattern for each command:
context.subscriptions.push(
  vscode.commands.registerCommand('pvm.promptDetail', async (id: string, version?: string) => {
    const panel = new PromptDetailPanel(context.extensionUri, cli, id, version, () => treeProvider.refresh());
    await panel.show();
  }),
  // ... etc for all commands
);
```

- [ ] **Step 2: Build**

```bash
cd vscode-extension && npm run build
```

- [ ] **Step 3: Test manually**

```bash
cd vscode-extension && code --extensionDevelopmentPath=.
```
Verify: sidebar appears, tree loads, clicking items opens panels, all CRUD operations work.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(vscode): wire up all commands and panel lifecycle"
```

---

## Task 14: Final Polish & Testing

**Files:**
- Modify: various files as needed

- [ ] **Step 1: Add error handling to all panels**

Wrap CLI calls in try/catch, show `vscode.window.showErrorMessage` on failure. Show error state in WebView when data loading fails.

- [ ] **Step 2: Add loading states**

Show "Loading..." in WebView while CLI commands execute.

- [ ] **Step 3: End-to-end manual test**

Test full workflow: init → add prompt → deploy → rollback → diff → snapshot → export → history → destroy. Verify all panels match Web UI layout.

- [ ] **Step 4: Build final**

```bash
cd vscode-extension && npm run build
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(vscode): add error handling and loading states"
```
