import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, badge, htmlPage, select, text } from "../templates/components";

export class SnapshotDiffPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private fromVersion?: string,
    private toVersion?: string,
  ) {
    super(extensionUri, "pvm.snapshotDiff", "Snapshot Diff");
  }

  async isResourceValid(): Promise<boolean> {
    const versions = await this.cli.listSnapshots();
    return (
      (this.fromVersion ? versions.includes(this.fromVersion) : true) &&
      (this.toVersion ? versions.includes(this.toVersion) : true)
    );
  }

  setVersions(fromVersion?: string, toVersion?: string): void {
    this.fromVersion = fromVersion;
    this.toVersion = toVersion;
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const versions = await this.cli.listSnapshots();
    if (!this.fromVersion) {
      this.fromVersion = versions[Math.max(versions.length - 2, 0)] ?? versions[0];
    }
    if (!this.toVersion) {
      this.toVersion = versions.at(-1) ?? versions[0];
    }

    const diff = await this.cli.diffSnapshot(this.fromVersion ?? "", this.toVersion ?? "");

    return `
      ${htmlPage(
        "Snapshot Diff",
        `${text(diff.from_version)} -> ${text(diff.to_version)}`,
        actionButton("Back", "secondary", "goBack"),
        logoSrc,
      )}

      <div class="summary-grid">
        <div class="summary-tile"><div class="count" style="color:var(--green)">${diff.added_ids.length}</div><div class="text-muted text-sm">Added</div></div>
        <div class="summary-tile"><div class="count" style="color:var(--red)">${diff.removed_ids.length}</div><div class="text-muted text-sm">Removed</div></div>
        <div class="summary-tile"><div class="count" style="color:var(--yellow)">${diff.changed_ids.length}</div><div class="text-muted text-sm">Changed</div></div>
      </div>

      ${renderIdSection("Added", diff.added_ids, "green")}
      ${renderIdSection("Removed", diff.removed_ids, "red")}
      ${renderChangedSection(diff.changed_ids)}

      <section class="card">
        <div class="section-title"><h3>Compare Other Versions</h3></div>
        <div class="flex wrap">
          <div class="select-wrap">${select(
            "snapshot-from",
            versions.map((version) => ({
              value: version,
              label: version,
              selected: version === this.fromVersion,
            })),
          )}</div>
          <div class="select-wrap">${select(
            "snapshot-to",
            versions.map((version) => ({
              value: version,
              label: version,
              selected: version === this.toVersion,
            })),
          )}</div>
          ${actionButton("Diff", "primary", "compare-selected")}
        </div>
      </section>
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    if (message.type === "compare") {
      this.fromVersion = String(message.fromVersion ?? "");
      this.toVersion = String(message.toVersion ?? "");
      await this.update();
      return;
    }

    if (message.type === "goBack") {
      await vscode.commands.executeCommand("pvm.dashboard");
    }
  }

  protected getScript(): string {
    return `
      document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-action='compare-selected']");
        if (!target) { return; }
        send("compare", {
          fromVersion: byId("snapshot-from").value,
          toVersion: byId("snapshot-to").value,
        });
      });
    `;
  }
}

function renderIdSection(title: string, ids: string[], tone: "green" | "red"): string {
  if (ids.length === 0) {
    return "";
  }
  return `
    <section class="card">
      <div class="section-title"><h3>${text(title)}</h3></div>
      <div class="stack">
        ${ids.map((id) => `<div>${badge(id, tone)}</div>`).join("")}
      </div>
    </section>
  `;
}

function renderChangedSection(changed: Array<{ id: string; from_version: string; to_version: string }>): string {
  if (changed.length === 0) {
    return "";
  }
  return `
    <section class="card">
      <div class="section-title"><h3>Changed</h3></div>
      <div class="stack">
        ${changed
          .map(
            (item) => `
              <div class="flex-between">
                <span class="mono">${text(item.id)}</span>
                <span class="text-muted text-sm">${text(item.from_version)} -> ${text(item.to_version)}</span>
              </div>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
