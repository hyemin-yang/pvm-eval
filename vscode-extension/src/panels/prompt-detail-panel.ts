import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import type { PromptGetResult, PromptInfoResult } from "../types";
import { BasePanel } from "./base-panel";
import { actionButton, badge, codeBlock, htmlPage, keyValueGrid, select, text } from "../templates/components";

export class PromptDetailPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly promptId: string,
    private readonly onRefresh: () => void,
    private currentVersion?: string,
  ) {
    super(extensionUri, `pvm.promptDetail.${promptId}`, `Prompt: ${promptId}`);
  }

  setVersion(version?: string): void {
    this.currentVersion = version;
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const info = await this.cli.getPromptInfo(this.promptId);
    const selectedVersion = this.resolveCurrentVersion(info);
    const promptData = selectedVersion ? await this.cli.getPrompt(this.promptId, selectedVersion) : null;

    const actions = [
      actionButton("New Version", "primary", "updatePrompt"),
      info.production ? actionButton("Rollback", "warning", "rollback") : "",
      actionButton("Delete", "danger", "delete"),
    ].join("");

    return `
      ${htmlPage(this.promptId, info.info.description || "", actions, logoSrc)}

      <div class="grid-sidebar">
        <div>
          ${renderVersionCard(info, selectedVersion)}
          ${renderDeployCard(info, selectedVersion)}
          ${renderDiffCard(info, selectedVersion)}
        </div>

        <div>
          ${promptData ? renderPromptContent(promptData) : `<section class="card"><p class="text-muted text-sm">No version selected.</p></section>`}
        </div>
      </div>
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    switch (message.type) {
      case "selectVersion":
        this.currentVersion = String(message.version ?? "");
        await this.update();
        return;
      case "deploy": {
        const version = String(message.version ?? "").trim();
        const result = await this.cli.deploy(this.promptId, version || undefined);
        if (!result.changed && result.reason === "already_deployed") {
          void vscode.window.showInformationMessage(`Version ${version} is already deployed.`);
        }
        this.onRefresh();
        await this.update();
        return;
      }
      case "rollback":
        if (
          (await vscode.window.showWarningMessage(
            `Rollback ${this.promptId} to the previous production version?`,
            { modal: true },
            "Rollback",
          )) !== "Rollback"
        ) {
          return;
        }
        await this.cli.rollback(this.promptId);
        this.onRefresh();
        await this.update();
        return;
      case "delete":
        if (
          (await vscode.window.showWarningMessage(
            `Delete ${this.promptId} and all versions?`,
            { modal: true },
            "Delete",
          )) !== "Delete"
        ) {
          return;
        }
        await this.cli.deletePrompt(this.promptId);
        this.onRefresh();
        void vscode.commands.executeCommand("pvm.dashboard");
        return;
      case "updatePrompt":
        await vscode.commands.executeCommand("pvm.promptUpdate", this.promptId);
        return;
      case "openDiff":
        await vscode.commands.executeCommand(
          "pvm.promptDiff",
          this.promptId,
          String(message.fromVersion ?? ""),
          String(message.toVersion ?? ""),
        );
        return;
      default:
        return;
    }
  }

  protected getScript(): string {
    return `
      document.addEventListener("click", (event) => {
        const deployTarget = event.target.closest("[data-action='deploy-selected']");
        if (deployTarget) {
          send("deploy", { version: byId("deploy-version").value });
          return;
        }
        const diffTarget = event.target.closest("[data-action='open-diff']");
        if (diffTarget) {
          send("openDiff", {
            fromVersion: byId("diff-from").value,
            toVersion: byId("diff-to").value,
          });
        }
      });
    `;
  }

  private resolveCurrentVersion(info: PromptInfoResult): string | undefined {
    if (this.currentVersion) {
      return this.currentVersion;
    }
    return info.production?.version ?? info.latest_version ?? undefined;
  }
}

function renderVersionCard(info: PromptInfoResult, currentVersion?: string): string {
  return `
    <section class="card">
      <div class="section-title"><h3>Versions</h3></div>
      <div class="version-list">
        ${[...info.versions]
          .reverse()
          .map((version) => {
            const tags: string[] = [];
            if (info.production?.version === version) {
              tags.push(badge("prod", "green"));
            }
            if (info.latest_version === version) {
              tags.push(badge("latest", "blue"));
            }
            return `
              <div class="version-item ${version === currentVersion ? "active" : ""}" data-action="selectVersion" data-payload='{"version":"${text(version)}"}'>
                <span class="mono">${text(version)}</span>
                <span class="flex wrap">${tags.join("")}</span>
              </div>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderDeployCard(info: PromptInfoResult, currentVersion?: string): string {
  return `
    <section class="card">
      <div class="section-title"><h3>Deploy</h3></div>
      <div class="stack">
        ${select(
          "deploy-version",
          [...info.versions].reverse().map((version) => ({
            value: version,
            label: version,
            selected: version === currentVersion,
          })),
        )}
        ${actionButton("Deploy", "primary", "deploy-selected")}
      </div>
    </section>
  `;
}

function renderDiffCard(info: PromptInfoResult, currentVersion?: string): string {
  if (info.versions.length < 2) {
    return "";
  }

  const fromVersion = info.versions[Math.max(info.versions.length - 2, 0)];
  const toVersion = currentVersion ?? info.versions.at(-1) ?? "";

  return `
    <section class="card">
      <div class="section-title"><h3>Diff</h3></div>
      <div class="stack">
        ${select(
          "diff-from",
          info.versions.map((version) => ({
            value: version,
            label: version,
            selected: version === fromVersion,
          })),
        )}
        ${select(
          "diff-to",
          info.versions.map((version) => ({
            value: version,
            label: version,
            selected: version === toVersion,
          })),
        )}
        ${actionButton("Diff", "secondary", "open-diff")}
      </div>
    </section>
  `;
}

function renderPromptContent(promptData: PromptGetResult): string {
  return `
    <section class="card">
      <div class="flex-between">
        <h3>Prompt ${badge(`v${promptData.version}`, "green")}</h3>
      </div>
      <div class="mt-4">${codeBlock(promptData.prompt)}</div>
    </section>

    <section class="card">
      <div class="section-title"><h3>LLM Config</h3></div>
      ${codeBlock(JSON.stringify(promptData.llm, null, 2))}
    </section>

    <section class="card">
      <div class="section-title"><h3>Metadata</h3></div>
      ${keyValueGrid([
        { key: "Author", value: text(promptData.metadata.author || "-") },
        { key: "Created", value: text(promptData.metadata.created_at) },
        { key: "Source File", value: `<span class="mono text-xs">${text(promptData.metadata.source_file)}</span>` },
        { key: "Template Checksum", value: `<span class="mono text-xs">${text(promptData.metadata.template_checksum)}</span>` },
      ])}
    </section>
  `;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
