import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import type { PromptSummary } from "../types";
import {
  DashboardItem,
  HistoryItem,
  PromptIdItem,
  PromptVersionItem,
  PromptsHeaderItem,
  SetupItem,
  SnapshotVersionItem,
  SnapshotsHeaderItem,
} from "./tree-items";

export class PvmTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly emitter = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.emitter.event;

  private promptCache = new Map<string, PromptSummary>();
  private snapshotCache: string[] = [];

  constructor(private readonly cli: PvmCli) {}

  refresh(): void {
    this.promptCache.clear();
    this.snapshotCache = [];
    this.emitter.fire();
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
    if (!element) {
      return this.getRootItems();
    }

    if (element instanceof PromptsHeaderItem) {
      const summaries = await this.loadPromptSummaries();
      return summaries.map(
        (summary) => new PromptIdItem(summary.id, summary.production?.version ?? null, summary.versions.length),
      );
    }

    if (element instanceof PromptIdItem) {
      const summary = await this.getPromptSummary(element.promptId);
      return [...summary.versions]
        .reverse()
        .map(
          (version) =>
            new PromptVersionItem(
              summary.id,
              version,
              summary.production?.version === version,
              summary.latest_version === version,
            ),
        );
    }

    if (element instanceof SnapshotsHeaderItem) {
      return [...this.snapshotCache].reverse().map((version) => new SnapshotVersionItem(version));
    }

    return [];
  }

  private async getRootItems(): Promise<vscode.TreeItem[]> {
    const integrity = await this.cli.checkIntegrity();
    if (!integrity.valid) {
      return [new SetupItem()];
    }

    const [summaries, snapshots] = await Promise.all([this.loadPromptSummaries(), this.cli.listSnapshots()]);
    this.snapshotCache = snapshots;

    return [
      new DashboardItem(),
      new PromptsHeaderItem(summaries.length),
      new SnapshotsHeaderItem(snapshots.length),
      new HistoryItem(),
    ];
  }

  private async loadPromptSummaries(): Promise<PromptSummary[]> {
    const summaries = await this.cli.getPromptSummaries();
    this.promptCache = new Map(summaries.map((summary) => [summary.id, summary]));
    return summaries;
  }

  private async getPromptSummary(promptId: string): Promise<PromptSummary> {
    const cached = this.promptCache.get(promptId);
    if (cached) {
      return cached;
    }
    const summary = await this.cli.getPromptInfo(promptId);
    this.promptCache.set(promptId, summary);
    return summary;
  }
}