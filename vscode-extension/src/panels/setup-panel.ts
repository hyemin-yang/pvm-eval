import * as vscode from "vscode";

import { PvmCli } from "../pvm-cli";
import { BasePanel } from "./base-panel";
import { actionButton, htmlPage, text } from "../templates/components";

export class SetupPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly onRefresh: () => void,
    private readonly onInitialized: () => void,
  ) {
    super(extensionUri, "pvm.setup", "PVM Setup");
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const integrity = await this.cli.checkIntegrity();
    const hasProjectDir = integrity.missing_dirs.every((entry) => entry !== ".pvm");
    const message = hasProjectDir
      ? "A .pvm directory exists but is incomplete. Destroy it and re-initialize."
      : "No pvm project found at this workspace. Initialize one to get started.";

    const actionBlock = hasProjectDir
      ? `
          <div class="notice notice-warning">${text(message)}</div>
          <div class="mt-4">${actionButton("Destroy Existing .pvm", "danger", "destroy")}</div>
        `
      : `
          <div class="notice">${text(message)}</div>
          <div class="mt-4 stack">
            <div>
              <label for="project-name">Project Name</label>
              <input id="project-name" value="my-project" />
            </div>
            <button class="button button-primary" data-ui-init="true">Initialize Project</button>
          </div>
        `;

    return `
      ${htmlPage("pvm", this.cli.getWorkspaceRoot(), undefined, logoSrc)}
      <section class="card" style="max-width:640px">
        ${actionBlock}
      </section>
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    if (message.type === "init") {
      const name = String(message.name ?? "my-project").trim() || "my-project";
      await this.cli.init(name);
      this.onRefresh();
      this.onInitialized();
      return;
    }

    if (message.type === "destroy") {
      const confirm = await vscode.window.showWarningMessage(
        "Destroy the existing .pvm directory?",
        { modal: true },
        "Destroy",
      );
      if (confirm !== "Destroy") {
        return;
      }
      await this.cli.destroyProjectDirectory();
      this.onRefresh();
      await this.update();
    }
  }

  protected getScript(): string {
    return `
      document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-ui-init='true']");
        if (!target) { return; }
        send("init", { name: byId("project-name").value });
      });
    `;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
