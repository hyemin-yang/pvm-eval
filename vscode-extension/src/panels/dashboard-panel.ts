import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, actionLink, badge, clickableTable, codeBlock, htmlPage, text } from "../templates/components";

export class DashboardPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly onRefresh: () => void,
  ) {
    super(extensionUri, "pvm.dashboard", "PVM Dashboard");
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.getLogoSrc();
    const [config, integrity, prompts, snapshots, projectTree] = await Promise.all([
      this.cli.loadProjectConfig(),
      this.cli.checkIntegrity(),
      this.cli.getPromptSummaries(),
      this.cli.listSnapshots(),
      this.cli.project(),
    ]);

    const promptTable = prompts.length
      ? clickableTable(
          ["ID", "Versions", "Production", "Created"],
          prompts.map((prompt) => ({
            action: "promptDetail",
            payload: { promptId: prompt.id },
            cells: [
              `<span class="mono">${text(prompt.id)}</span>`,
              String(prompt.versions.length),
              prompt.production ? badge(`v${prompt.production.version}`, "green") : badge("not deployed", "gray"),
              text(prompt.info.created_at),
            ],
          })),
        )
      : `<p class="text-muted text-sm">No prompts yet.</p>`;

    const snapshotsHtml = snapshots.length
      ? snapshots
          .slice(-5)
          .reverse()
          .map(
            (version) => `
              <div class="flex-between mt-2">
                ${actionLink(version, "snapshotDetail", { version }, "mono")}
              </div>
            `,
          )
          .join("")
      : `<p class="text-muted text-sm">No snapshots yet.</p>`;

    return `
      ${htmlPage(
        config?.name ?? "pvm",
        this.cli.getWorkspaceRoot(),
        [
          actionButton("Add Prompt", "primary", "addPrompt"),
          actionButton("Create Snapshot", "secondary", "createSnapshot"),
          actionButton("History", "secondary", "history"),
        ].join(""),
        logoSrc,
      )}

      <section class="card">
        <div class="flex-between wrap">
          <div class="stack">
            <div class="text-muted text-sm">Project ID</div>
            <div class="mono text-sm">${text(config?.project_id ?? "-")}</div>
          </div>
          <div class="stack">
            <div class="text-muted text-sm">Created</div>
            <div class="text-sm">${text(config?.created_at ?? "-")}</div>
          </div>
          <div class="stack">
            <div class="text-muted text-sm">Integrity</div>
            <div>${integrity.valid ? badge("Valid", "green") : badge("Corrupted", "red")}</div>
          </div>
          <div class="flex wrap">
            ${actionButton("Reset", "warning", "reset")}
            ${actionButton("Destroy", "danger", "destroy")}
          </div>
        </div>
      </section>

      <section class="card">
        <div class="flex-between">
          <h3>Prompts</h3>
          <div class="stat-number">${prompts.length}</div>
        </div>
        <div class="mt-4">${promptTable}</div>
      </section>

      <section class="card">
        <div class="flex-between">
          <h3>Snapshots</h3>
          <div class="stat-number">${snapshots.length}</div>
        </div>
        <div class="mt-4">${snapshotsHtml}</div>
      </section>

      <section class="card">
        <div class="section-title"><h3>Project Tree</h3></div>
        <div class="mt-4">${codeBlock(projectTree)}</div>
      </section>
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    switch (message.type) {
      case "addPrompt":
        await vscode.commands.executeCommand("pvm.addPrompt");
        return;
      case "createSnapshot":
        await vscode.commands.executeCommand("pvm.createSnapshot");
        return;
      case "promptDetail":
        await vscode.commands.executeCommand("pvm.promptDetail", message.promptId);
        return;
      case "snapshotDetail":
        await vscode.commands.executeCommand("pvm.snapshotDetail", message.version);
        return;
      case "history":
        await vscode.commands.executeCommand("pvm.showHistory");
        return;
      case "reset":
        if (
          (await vscode.window.showWarningMessage(
            "Reset project? All prompts and snapshots will be removed.",
            { modal: true },
            "Reset",
          )) !== "Reset"
        ) {
          return;
        }
        await this.cli.reset();
        this.onRefresh();
        await this.update();
        return;
      case "destroy":
        if (
          (await vscode.window.showWarningMessage(
            "Destroy project? The .pvm directory will be permanently deleted.",
            { modal: true },
            "Destroy",
          )) !== "Destroy"
        ) {
          return;
        }
        await this.cli.destroy();
        this.onRefresh();
        await vscode.commands.executeCommand("pvm.init");
        return;
      default:
        return;
    }
  }

  private getLogoSrc(): string {
    return this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
  }

}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
