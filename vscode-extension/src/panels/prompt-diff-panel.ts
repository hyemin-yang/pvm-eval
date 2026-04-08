import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, badge, codeBlock, htmlPage, select, text } from "../templates/components";

export class PromptDiffPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly promptId: string,
    private fromVersion?: string,
    private toVersion?: string,
  ) {
    super(extensionUri, `pvm.promptDiff.${promptId}`, `Prompt Diff: ${promptId}`);
  }

  async isResourceValid(): Promise<boolean> {
    const ids = await this.cli.listPromptIds();
    return ids.includes(this.promptId);
  }

  setVersions(fromVersion?: string, toVersion?: string): void {
    this.fromVersion = fromVersion;
    this.toVersion = toVersion;
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const versions = await this.cli.listPromptVersions(this.promptId);
    if (!this.fromVersion) {
      this.fromVersion = versions[Math.max(versions.length - 2, 0)] ?? versions[0];
    }
    if (!this.toVersion) {
      this.toVersion = versions.at(-1) ?? versions[0];
    }

    const diffResult = await this.cli.diffPrompt(this.promptId, this.fromVersion ?? "", this.toVersion ?? "");

    return `
      ${htmlPage(
        this.promptId,
        `Comparing ${text(diffResult.from_version)} -> ${text(diffResult.to_version)}`,
        actionButton("Back to Prompt", "secondary", "openPrompt"),
        logoSrc,
      )}

      <section class="card">
        <div class="flex wrap">
          ${diffResult.changed ? badge(`+${diffResult.lines_added} lines`, "green") : badge("No changes", "gray")}
          ${diffResult.changed ? badge(`-${diffResult.lines_removed} lines`, "red") : ""}
          ${badge(`Length delta: ${diffResult.prompt_length_delta}`, "gray")}
          ${diffResult.model_config_changed ? badge("Model config changed", "yellow") : badge("Model config unchanged", "gray")}
        </div>
      </section>

      <section class="card">
        <div class="section-title"><h3>Diff</h3></div>
        ${codeBlock(diffResult.unified_diff)}
      </section>

      <section class="card">
        <div class="section-title"><h3>Compare Other Versions</h3></div>
        <div class="flex wrap">
          <div class="select-wrap">${select(
            "diff-from",
            versions.map((version) => ({
              value: version,
              label: version,
              selected: version === this.fromVersion,
            })),
          )}</div>
          <div class="select-wrap">${select(
            "diff-to",
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

    if (message.type === "openPrompt") {
      await vscode.commands.executeCommand("pvm.promptDetail", this.promptId);
    }
  }

  protected getScript(): string {
    return `
      document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-action='compare-selected']");
        if (!target) { return; }
        send("compare", {
          fromVersion: byId("diff-from").value,
          toVersion: byId("diff-to").value,
        });
      });
    `;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
