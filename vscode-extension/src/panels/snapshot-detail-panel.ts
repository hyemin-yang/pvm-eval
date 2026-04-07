import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, codeBlock, htmlPage, keyValueGrid, text } from "../templates/components";

export class SnapshotDetailPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly version: string,
  ) {
    super(extensionUri, `pvm.snapshotDetail.${version}`, `Snapshot: ${version}`);
  }

  async isResourceValid(): Promise<boolean> {
    const versions = await this.cli.listSnapshots();
    return versions.includes(this.version);
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const [manifest, snapshotData] = await Promise.all([
      this.cli.getSnapshot(this.version),
      this.cli.readSnapshot(this.version),
    ]);

    const promptCards = Object.entries(snapshotData.prompts)
      .map(
        ([promptId, prompt]) => `
          <section class="card">
            <div class="flex-between wrap">
              <h3>${text(promptId)}</h3>
              <span class="mono text-sm">v${text(prompt.version)}</span>
            </div>
            <div class="mt-4">${codeBlock(prompt.prompt)}</div>
            <div class="mt-4">${codeBlock(JSON.stringify(prompt.llm, null, 2))}</div>
          </section>
        `,
      )
      .join("");

    return `
      ${htmlPage(
        `Snapshot ${this.version}`,
        manifest.created_at,
        [
          actionButton("Export ZIP", "primary", "exportSnapshot"),
          actionButton("Back", "secondary", "goBack"),
        ].join(""),
        logoSrc,
      )}

      <section class="card">
        ${keyValueGrid([
          { key: "Prompt Count", value: text(String(manifest.prompt_count)) },
          { key: "Checksum", value: `<span class="mono text-xs">${text(manifest.snapshot_checksum)}</span>` },
          { key: "Created", value: text(manifest.created_at) },
        ])}
      </section>

      ${promptCards || `<section class="card"><p class="text-muted text-sm">No prompts in snapshot.</p></section>`}
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    if (message.type === "goBack") {
      await vscode.commands.executeCommand("pvm.dashboard");
      return;
    }

    if (message.type === "exportSnapshot") {
      const defaultUri = vscode.Uri.file(
        vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
          ? `${vscode.workspace.workspaceFolders[0].uri.fsPath}\\snapshot-${this.version}.zip`
          : `snapshot-${this.version}.zip`,
      );
      const target = await vscode.window.showSaveDialog({
        defaultUri,
        filters: {
          ZIP: ["zip"],
        },
      });
      if (!target) {
        return;
      }
      await this.cli.exportSnapshot(this.version, target.fsPath);
      void vscode.window.showInformationMessage(`Snapshot exported to ${target.fsPath}`);
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
