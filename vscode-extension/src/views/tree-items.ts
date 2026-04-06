import * as vscode from "vscode";

export class SetupItem extends vscode.TreeItem {
  readonly contextValue = "setup";

  constructor() {
    super("Initialize PVM Project", vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon("tools");
    this.command = {
      command: "pvm.init",
      title: "Initialize Project",
    };
  }
}

export class DashboardItem extends vscode.TreeItem {
  readonly contextValue = "dashboard";

  constructor() {
    super("Dashboard", vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon("dashboard");
    this.command = {
      command: "pvm.dashboard",
      title: "Dashboard",
    };
  }
}

export class HistoryItem extends vscode.TreeItem {
  readonly contextValue = "history";

  constructor() {
    super("History", vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon("history");
    this.command = {
      command: "pvm.showHistory",
      title: "History",
    };
  }
}

export class PromptsHeaderItem extends vscode.TreeItem {
  readonly contextValue = "promptsHeader";

  constructor(count: number) {
    super(`Prompts (${count})`, vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon("note");
  }
}

export class PromptIdItem extends vscode.TreeItem {
  readonly contextValue = "promptId";

  constructor(
    public readonly promptId: string,
    public readonly productionVersion: string | null,
    versionCount: number,
  ) {
    super(promptId, vscode.TreeItemCollapsibleState.Collapsed);
    this.iconPath = new vscode.ThemeIcon("file");
    this.description = productionVersion ? `prod: ${productionVersion}` : `${versionCount} versions`;
    this.tooltip = `${promptId} (${versionCount} versions)`;
    this.command = {
      command: "pvm.promptDetail",
      title: "View Prompt",
      arguments: [promptId],
    };
  }
}

export class PromptVersionItem extends vscode.TreeItem {
  readonly contextValue = "promptVersion";

  constructor(
    public readonly promptId: string,
    public readonly version: string,
    isProduction: boolean,
    isLatest: boolean,
  ) {
    super(`v${version}`, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(isProduction ? "circle-filled" : "circle-outline");
    const badges: string[] = [];
    if (isProduction) {
      badges.push("prod");
    }
    if (isLatest) {
      badges.push("latest");
    }
    this.description = badges.join(" ");
    this.command = {
      command: "pvm.promptDetail",
      title: "View Prompt Version",
      arguments: [promptId, version],
    };
  }
}

export class SnapshotsHeaderItem extends vscode.TreeItem {
  readonly contextValue = "snapshotsHeader";

  constructor(count: number) {
    super(`Snapshots (${count})`, vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon("archive");
  }
}

export class SnapshotVersionItem extends vscode.TreeItem {
  readonly contextValue = "snapshotVersion";

  constructor(public readonly version: string) {
    super(`v${version}`, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon("package");
    this.command = {
      command: "pvm.snapshotDetail",
      title: "View Snapshot",
      arguments: [version],
    };
  }
}
