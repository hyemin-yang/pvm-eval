import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, actionLink, badge, htmlPage, select, table, text } from "../templates/components";

export class HistoryPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private selectedPromptId = "",
  ) {
    super(extensionUri, "pvm.history", "PVM History");
  }

  setSelectedPromptId(promptId: string): void {
    this.selectedPromptId = promptId;
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const [promptIds, entries] = await Promise.all([
      this.cli.listPromptIds(),
      this.cli.readHistory(this.selectedPromptId || undefined),
    ]);

    const header = htmlPage(
      "History",
      this.selectedPromptId ? `Prompt: ${text(this.selectedPromptId)}` : "Snapshot history",
      actionButton("Refresh", "secondary", "filter-selected"),
      logoSrc,
    );

    const filter = `
      <section class="card">
        <label for="history-filter">Filter</label>
        <div class="flex wrap">
          <div style="min-width:260px; flex:1">
            ${select("history-filter", [
              { value: "", label: "All (Snapshot history)", selected: !this.selectedPromptId },
              ...promptIds.map((promptId) => ({
                value: promptId,
                label: promptId,
                selected: promptId === this.selectedPromptId,
              })),
            ])}
          </div>
          ${actionButton("Apply", "primary", "filter-selected")}
        </div>
      </section>
    `;

    const rows = entries
      .slice()
      .reverse()
      .map((entry) => [
        `<span class="mono text-xs">${text(entry.ts)}</span>`,
        renderEventBadge(entry.event),
        entry.id ? actionLink(entry.id, "openPrompt", { promptId: entry.id }, "mono") : text(entry.version ?? "-"),
        text(renderDetails(entry)),
      ]);

    const tableHtml = rows.length
      ? table(["Time", "Event", "ID", "Details"], rows)
      : `<section class="card"><p class="text-muted text-sm">No history entries.</p></section>`;

    return `${header}${filter}${tableHtml}`;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    if (message.type === "filter") {
      this.selectedPromptId = String(message.promptId ?? "");
      await this.update();
      return;
    }

    if (message.type === "openPrompt" && message.promptId) {
      await vscode.commands.executeCommand("pvm.promptDetail", message.promptId);
    }
  }

  protected getScript(): string {
    return `
      document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-action='filter-selected']");
        if (!target) { return; }
        send("filter", { promptId: byId("history-filter").value });
      });
    `;
  }
}

function renderEventBadge(event: string): string {
  switch (event) {
    case "add":
      return badge("add", "blue");
    case "deploy":
      return badge("deploy", "green");
    case "rollback":
      return badge("rollback", "yellow");
    case "create":
      return badge("snapshot", "gray");
    default:
      return badge(event, "gray");
  }
}

function renderDetails(entry: { event: string; version?: string; from_version?: string | null; to_version?: string; prompt_count?: number }): string {
  switch (entry.event) {
    case "add":
      return `version ${entry.version ?? "-"}`;
    case "deploy":
    case "rollback":
      return `${entry.from_version ?? "none"} -> ${entry.to_version ?? "-"}`;
    case "create":
      return `${entry.prompt_count ?? 0} prompts`;
    default:
      return "";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
