import * as vscode from "vscode";

import { getStyles } from "../templates/styles";

export abstract class BasePanel {
  protected panel: vscode.WebviewPanel | undefined;

  constructor(
    protected readonly extensionUri: vscode.Uri,
    private readonly viewType: string,
    private readonly title: string,
  ) {}

  async show(column: vscode.ViewColumn = vscode.ViewColumn.One): Promise<void> {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(this.viewType, this.title, column, {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [this.extensionUri],
      });
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
      this.panel.webview.onDidReceiveMessage((message) => {
        void this.onMessage(message);
      });
    } else {
      this.panel.reveal(column);
    }

    await this.update();
  }

  async update(): Promise<void> {
    if (!this.panel) {
      return;
    }
    const body = await this.getHtmlContent(this.panel.webview);
    this.panel.webview.html = this.wrapHtml(body);
  }

  protected abstract getHtmlContent(webview: vscode.Webview): Promise<string>;

  protected async onMessage(_message: unknown): Promise<void> {}

  async isResourceValid(): Promise<boolean> {
    return true;
  }

  dispose(): void {
    this.panel?.dispose();
  }

  private wrapHtml(body: string): string {
    const nonce = createNonce();
    const csp = `
      default-src 'none';
      img-src https: data: ${this.panel?.webview.cspSource};
      style-src 'nonce-${nonce}' 'unsafe-inline';
      font-src ${this.panel?.webview.cspSource};
      script-src 'nonce-${nonce}' 'unsafe-inline';
      connect-src ${this.panel?.webview.cspSource};
    `;
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style nonce="${nonce}">${getStyles()}</style>
</head>
<body>
  <div class="space-y">${body}</div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    function send(type, data = {}) { vscode.postMessage({ type, ...data }); }
    function byId(id) { return document.getElementById(id); }
    document.addEventListener("click", (event) => {
      const target = event.target.closest("[data-action]");
      if (!target) { return; }
      event.preventDefault();
      const action = target.getAttribute("data-action");
      const payload = target.getAttribute("data-payload");
      let data = {};
      if (payload) {
        try { data = JSON.parse(payload); } catch {}
      }
      if (action) {
        send(action, data);
      }
    });
    ${this.getScript()}
  </script>
</body>
</html>`;
  }

  protected getScript(): string {
    return "";
  }
}

function createNonce(): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let index = 0; index < 32; index += 1) {
    result += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return result;
}
