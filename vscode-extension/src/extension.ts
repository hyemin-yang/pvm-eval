import * as path from "node:path";

import * as vscode from "vscode";

import { PvmCli } from "./pvm-cli";
import type { BumpLevel } from "./types";
import { BasePanel } from "./panels/base-panel";
import { DashboardPanel } from "./panels/dashboard-panel";
import { HistoryPanel } from "./panels/history-panel";
import { PromptDetailPanel } from "./panels/prompt-detail-panel";
import { PromptDiffPanel } from "./panels/prompt-diff-panel";
import { PromptFormPanel } from "./panels/prompt-form-panel";
import { SetupPanel } from "./panels/setup-panel";
import { SnapshotDetailPanel } from "./panels/snapshot-detail-panel";
import { SnapshotDiffPanel } from "./panels/snapshot-diff-panel";
import { PvmTreeProvider } from "./views/pvm-tree-provider";
import { PromptIdItem, PromptVersionItem, SnapshotVersionItem } from "./views/tree-items";

export function activate(context: vscode.ExtensionContext): void {
  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }

  const cli = new PvmCli(workspaceRoot);
  const treeProvider = new PvmTreeProvider(cli);
  const setupPanels = new Map<string, SetupPanel>();
  const dashboardPanels = new Map<string, DashboardPanel>();
  const addPromptPanels = new Map<string, PromptFormPanel>();
  const historyPanels = new Map<string, HistoryPanel>();
  const snapshotDiffPanels = new Map<string, SnapshotDiffPanel>();
  const promptDetailPanels = new Map<string, PromptDetailPanel>();
  const promptDiffPanels = new Map<string, PromptDiffPanel>();
  const promptUpdatePanels = new Map<string, PromptFormPanel>();
  const snapshotDetailPanels = new Map<string, SnapshotDetailPanel>();
  let currentMainPanel: BasePanel | undefined;

  context.subscriptions.push(vscode.window.registerTreeDataProvider("pvmExplorer", treeProvider));

  const refresh = () => treeProvider.refresh();
  const showMainPanel = async (panel: BasePanel): Promise<void> => {
    if (currentMainPanel && currentMainPanel !== panel) {
      currentMainPanel.dispose();
    }
    currentMainPanel = panel;
    await panel.show(vscode.ViewColumn.One);
  };

  context.subscriptions.push(
    vscode.commands.registerCommand("pvm.refresh", () => refresh()),

    vscode.commands.registerCommand("pvm.init", () =>
      runGuarded(async () => {
        const panel = getSingletonPanel(setupPanels, "setup", () =>
          new SetupPanel(context.extensionUri, cli, refresh, () => {
            refresh();
            void vscode.commands.executeCommand("pvm.dashboard");
          }),
        );
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.dashboard", () =>
      runGuarded(async () => {
        const valid = await cli.isProjectValid();
        if (!valid) {
          await vscode.commands.executeCommand("pvm.init");
          return;
        }
        const panel = getSingletonPanel(dashboardPanels, "dashboard", () =>
          new DashboardPanel(context.extensionUri, cli, refresh),
        );
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.addPrompt", () =>
      runGuarded(async () => {
        if (!(await cli.isProjectValid())) {
          await vscode.commands.executeCommand("pvm.init");
          return;
        }
        const panel = getSingletonPanel(addPromptPanels, "addPrompt", () =>
          new PromptFormPanel(context.extensionUri, cli, "add", refresh),
        );
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.createSnapshot", () =>
      runGuarded(async () => {
        const bump = await vscode.window.showQuickPick(["patch", "minor", "major"], {
          placeHolder: "Select snapshot bump level",
        });
        if (!bump) {
          return;
        }
        const result = await cli.createSnapshot(bump as BumpLevel);
        if (!("version" in result) || !result.version) {
          void vscode.window.showInformationMessage("No deployed prompts found. Deploy prompts before creating a snapshot.");
          return;
        }
        refresh();
        void vscode.window.showInformationMessage(`Snapshot ${result.version} created.`);
        await vscode.commands.executeCommand("pvm.snapshotDetail", result.version);
      }),
    ),

    vscode.commands.registerCommand("pvm.destroy", () =>
      runGuarded(async () => {
        const confirm = await vscode.window.showWarningMessage(
          "Destroy project? The .pvm directory will be permanently deleted.",
          { modal: true },
          "Destroy",
        );
        if (confirm !== "Destroy") {
          return;
        }
        await cli.destroy();
        refresh();
        await vscode.commands.executeCommand("pvm.init");
      }),
    ),

    vscode.commands.registerCommand("pvm.reset", () =>
      runGuarded(async () => {
        const confirm = await vscode.window.showWarningMessage(
          "Reset project? All prompts and snapshots will be removed.",
          { modal: true },
          "Reset",
        );
        if (confirm !== "Reset") {
          return;
        }
        await cli.reset();
        refresh();
        await vscode.commands.executeCommand("pvm.dashboard");
      }),
    ),

    vscode.commands.registerCommand("pvm.showHistory", (arg?: unknown) =>
      runGuarded(async () => {
        const selectedPromptId = extractPromptId(arg);
        const panel = getSingletonPanel(historyPanels, "history", () =>
          new HistoryPanel(context.extensionUri, cli, selectedPromptId ?? ""),
        );
        panel.setSelectedPromptId(selectedPromptId ?? "");
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptDetail", (arg1?: unknown, arg2?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg1);
        const version = extractVersion(arg1) ?? extractString(arg2);
        if (!promptId) {
          return;
        }
        const panel = getMappedPanel(promptDetailPanels, promptId, () =>
          new PromptDetailPanel(context.extensionUri, cli, promptId, refresh, version),
        );
        panel.setVersion(version);
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptUpdate", (arg?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg);
        if (!promptId) {
          return;
        }
        const panel = getMappedPanel(promptUpdatePanels, promptId, () =>
          new PromptFormPanel(context.extensionUri, cli, "update", refresh, promptId),
        );
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptDiff", (arg1?: unknown, arg2?: unknown, arg3?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg1);
        if (!promptId) {
          return;
        }
        const fromVersion =
          arg1 instanceof PromptVersionItem ? arg1.version : extractString(arg2);
        const toVersion = extractString(arg3);
        const panel = getMappedPanel(promptDiffPanels, promptId, () =>
          new PromptDiffPanel(context.extensionUri, cli, promptId, fromVersion, toVersion),
        );
        panel.setVersions(fromVersion, toVersion);
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptDeploy", (arg?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg);
        if (!promptId) {
          return;
        }

        let version = extractVersion(arg);
        if (!version) {
          const versions = [...(await cli.listPromptVersions(promptId))].reverse();
          version = await vscode.window.showQuickPick(versions, {
            placeHolder: `Select version to deploy for ${promptId}`,
          });
        }
        if (!version) {
          return;
        }

        await cli.deploy(promptId, version);
        refresh();
        void vscode.window.showInformationMessage(`${promptId} deployed to ${version}.`);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptRollback", (arg?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg);
        if (!promptId) {
          return;
        }
        const confirm = await vscode.window.showWarningMessage(
          `Rollback ${promptId} to the previous production version?`,
          { modal: true },
          "Rollback",
        );
        if (confirm !== "Rollback") {
          return;
        }
        await cli.rollback(promptId);
        refresh();
        void vscode.window.showInformationMessage(`${promptId} rolled back.`);
      }),
    ),

    vscode.commands.registerCommand("pvm.promptDelete", (arg?: unknown) =>
      runGuarded(async () => {
        const promptId = extractPromptId(arg);
        if (!promptId) {
          return;
        }
        const confirm = await vscode.window.showWarningMessage(
          `Delete ${promptId} and all versions?`,
          { modal: true },
          "Delete",
        );
        if (confirm !== "Delete") {
          return;
        }
        await cli.deletePrompt(promptId);
        refresh();
        void vscode.window.showInformationMessage(`${promptId} deleted.`);
      }),
    ),

    vscode.commands.registerCommand("pvm.snapshotDetail", (arg?: unknown) =>
      runGuarded(async () => {
        const version = extractVersion(arg) ?? extractString(arg);
        if (!version) {
          return;
        }
        const panel = getMappedPanel(snapshotDetailPanels, version, () =>
          new SnapshotDetailPanel(context.extensionUri, cli, version),
        );
        await showMainPanel(panel);
      }),
    ),

    vscode.commands.registerCommand("pvm.snapshotExport", (arg?: unknown) =>
      runGuarded(async () => {
        const version = extractVersion(arg) ?? extractString(arg);
        if (!version) {
          return;
        }
        const target = await vscode.window.showSaveDialog({
          defaultUri: vscode.Uri.file(path.join(workspaceRoot, `snapshot-${version}.zip`)),
          filters: { ZIP: ["zip"] },
        });
        if (!target) {
          return;
        }
        await cli.exportSnapshot(version, target.fsPath);
        void vscode.window.showInformationMessage(`Snapshot exported to ${target.fsPath}`);
      }),
    ),

    vscode.commands.registerCommand("pvm.snapshotDiff", (arg?: unknown) =>
      runGuarded(async () => {
        const versions = await cli.listSnapshots();
        if (versions.length < 2) {
          void vscode.window.showInformationMessage("At least two snapshots are required.");
          return;
        }

        const toVersion = extractVersion(arg) ?? versions.at(-1);
        const fromVersion =
          (await vscode.window.showQuickPick(versions.filter((version) => version !== toVersion), {
            placeHolder: "Select base snapshot version",
          })) ?? versions[Math.max(versions.length - 2, 0)];

        if (!fromVersion || !toVersion) {
          return;
        }

        const panel = getSingletonPanel(snapshotDiffPanels, "snapshotDiff", () =>
          new SnapshotDiffPanel(context.extensionUri, cli, fromVersion, toVersion),
        );
        panel.setVersions(fromVersion, toVersion);
        await showMainPanel(panel);
      }),
    ),
  );
}

export function deactivate(): void {}

async function runGuarded(work: () => Promise<void>): Promise<void> {
  try {
    await work();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    void vscode.window.showErrorMessage(message);
  }
}

function getWorkspaceRoot(): string | null {
  const folder = vscode.workspace.workspaceFolders?.[0];
  return folder?.uri.fsPath ?? null;
}

function extractPromptId(value: unknown): string | undefined {
  if (value instanceof PromptIdItem || value instanceof PromptVersionItem) {
    return value.promptId;
  }
  return extractString(value);
}

function extractVersion(value: unknown): string | undefined {
  if (value instanceof PromptVersionItem || value instanceof SnapshotVersionItem) {
    return value.version;
  }
  return undefined;
}

function extractString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function getSingletonPanel<T>(
  registry: Map<string, T>,
  key: string,
  create: () => T,
): T {
  const existing = registry.get(key);
  if (existing) {
    return existing;
  }
  const panel = create();
  registry.set(key, panel);
  return panel;
}

function getMappedPanel<T>(
  registry: Map<string, T>,
  key: string,
  create: () => T,
): T {
  const existing = registry.get(key);
  if (existing) {
    return existing;
  }
  const panel = create();
  registry.set(key, panel);
  return panel;
}
