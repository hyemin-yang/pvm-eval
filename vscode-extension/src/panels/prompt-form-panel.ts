import * as vscode from "vscode";
import * as yaml from "yaml";

import { PvmCli } from "../pvm-cli";
import type { BumpLevel } from "../types";
import { BasePanel } from "./base-panel";
import { actionButton, htmlPage, text } from "../templates/components";

type PromptFormMode = "add" | "update";

export class PromptFormPanel extends BasePanel {
  constructor(
    extensionUri: vscode.Uri,
    private readonly cli: PvmCli,
    private readonly mode: PromptFormMode,
    private readonly onRefresh: () => void,
    private readonly promptId?: string,
  ) {
    super(
      extensionUri,
      mode === "add" ? "pvm.promptAdd" : `pvm.promptUpdate.${promptId ?? "unknown"}`,
      mode === "add" ? "Add Prompt" : `Update Prompt: ${promptId ?? ""}`,
    );
  }

  protected async getHtmlContent(): Promise<string> {
    const logoSrc = this.panel!.webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "logo.svg")).toString();
    const template =
      this.mode === "add"
        ? await this.cli.loadDefaultTemplate()
        : await this.cli.loadPromptTemplate(this.promptId ?? "");

    const yamlContent = toYamlString(template);

    return `
      ${htmlPage(
        this.mode === "add" ? "Add Prompt" : this.promptId ?? "Update Prompt",
        this.mode === "add" ? "Create a new immutable prompt version." : "Create a new version from the current template.",
        undefined,
        logoSrc,
      )}

      <section class="card">
        <div class="tabs">
          <button class="tab active" id="tab-form" data-ui-tab="form">Form</button>
          <button class="tab" id="tab-upload" data-ui-tab="upload">File Upload</button>
          <button class="tab" id="tab-editor" data-ui-tab="editor">YAML Editor</button>
        </div>

        <div id="panel-form" class="stack">
          ${renderFormFields(template, this.mode === "update")}
          <div class="mt-4">${actionButton(this.mode === "add" ? "Add Prompt" : "Update Version", "primary", "submit-form")}</div>
        </div>

        <div id="panel-upload" class="stack hidden">
          <div>
            <label for="template-file">YAML Template File</label>
            <input id="template-file" type="file" accept=".yaml,.yml" />
          </div>
          ${renderBumpField()}
          <div class="mt-4">${actionButton(this.mode === "add" ? "Add Prompt" : "Update Version", "primary", "submit-upload")}</div>
        </div>

        <div id="panel-editor" class="stack hidden">
          <div>
            <label for="yaml-content">YAML Template</label>
            <textarea id="yaml-content">${text(yamlContent)}</textarea>
          </div>
          ${renderBumpField()}
          <div class="mt-4">${actionButton(this.mode === "add" ? "Add Prompt" : "Update Version", "primary", "submit-editor")}</div>
        </div>
      </section>
    `;
  }

  protected async onMessage(message: unknown): Promise<void> {
    if (!isRecord(message)) {
      return;
    }

    switch (message.type) {
      case "submitForm": {
        const template = {
          id: this.mode === "update" ? this.promptId : String(message.prompt_id ?? ""),
          description: String(message.description ?? ""),
          author: String(message.author ?? ""),
          llm: {
            provider: String(message.llm_provider ?? ""),
            model: String(message.llm_model ?? ""),
          },
          prompt: String(message.prompt_text ?? ""),
        } as Record<string, unknown>;

        const params: Record<string, unknown> = {};
        const temperature = String(message.temperature ?? "").trim();
        const maxTokens = String(message.max_tokens ?? "").trim();
        if (temperature) {
          params.temperature = Number(temperature);
        }
        if (maxTokens) {
          params.max_tokens = Number(maxTokens);
        }
        if (Object.keys(params).length > 0) {
          (template.llm as Record<string, unknown>).params = params;
        }

        const extraFields = Array.isArray(message.extra_fields) ? message.extra_fields : [];
        for (const item of extraFields) {
          if (!isRecord(item)) {
            continue;
          }
          const key = String(item.key ?? "").trim();
          const value = String(item.value ?? "").trim();
          if (key && value) {
            template[key] = value;
          }
        }

        removeEmptyKeys(template);
        const result = await this.cli.addTemplateObject(template, parseBumpLevel(message.bump_level));
        this.onRefresh();
        await vscode.commands.executeCommand("pvm.promptDetail", result.id);
        return;
      }
      case "submitEditor": {
        const result = await this.cli.addTemplateContent(
          String(message.yaml_content ?? ""),
          parseBumpLevel(message.bump_level),
        );
        this.onRefresh();
        await vscode.commands.executeCommand("pvm.promptDetail", result.id);
        return;
      }
      case "submitUpload": {
        const content = String(message.content ?? "");
        const result = await this.cli.addTemplateContent(content, parseBumpLevel(message.bump_level));
        this.onRefresh();
        await vscode.commands.executeCommand("pvm.promptDetail", result.id);
        return;
      }
      default:
        return;
    }
  }

  protected getScript(): string {
    return `
      function switchTab(tab) {
        ["form", "upload", "editor"].forEach((name) => {
          byId("panel-" + name).classList.toggle("hidden", name !== tab);
          byId("tab-" + name).classList.toggle("active", name === tab);
        });
      }

      function collectExtraFields() {
        return Array.from(document.querySelectorAll(".extra-field")).map((row) => ({
          key: row.querySelector("[data-role='key']").value,
          value: row.querySelector("[data-role='value']").value,
        }));
      }

      function selectedBump() {
        const checked = document.querySelector("input[name='bump_level']:checked");
        return checked ? checked.value : "patch";
      }

      function submitForm() {
        send("submitForm", {
          prompt_id: byId("prompt-id") ? byId("prompt-id").value : "",
          prompt_text: byId("prompt-text").value,
          llm_provider: byId("llm-provider").value,
          llm_model: byId("llm-model").value,
          description: byId("description").value,
          author: byId("author").value,
          temperature: byId("temperature").value,
          max_tokens: byId("max-tokens").value,
          bump_level: selectedBump(),
          extra_fields: collectExtraFields(),
        });
      }

      function submitEditor() {
        send("submitEditor", {
          yaml_content: byId("yaml-content").value,
          bump_level: selectedBump(),
        });
      }

      async function submitUpload() {
        const fileInput = byId("template-file");
        if (!fileInput.files || !fileInput.files[0]) {
          return;
        }
        const content = await fileInput.files[0].text();
        send("submitUpload", {
          content,
          bump_level: selectedBump(),
        });
      }

      function addExtraField(key = "", value = "") {
        const container = byId("extra-fields");
        const row = document.createElement("div");
        row.className = "extra-field flex";
        row.innerHTML = \`
          <input data-role="key" placeholder="key" value="\${key}">
          <input data-role="value" placeholder="value" value="\${value}">
          <button class="button button-danger" type="button">Remove</button>
        \`;
        row.querySelector("button").addEventListener("click", () => row.remove());
        container.appendChild(row);
      }

      window.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-ui-tab]").forEach((element) => {
          element.addEventListener("click", () => switchTab(element.getAttribute("data-ui-tab")));
        });
        document.querySelectorAll("[data-action='submit-form']").forEach((element) => {
          element.addEventListener("click", submitForm);
        });
        document.querySelectorAll("[data-action='submit-editor']").forEach((element) => {
          element.addEventListener("click", submitEditor);
        });
        document.querySelectorAll("[data-action='submit-upload']").forEach((element) => {
          element.addEventListener("click", submitUpload);
        });
        document.querySelectorAll("[data-ui-add-extra]").forEach((element) => {
          element.addEventListener("click", () => addExtraField());
        });
        document.querySelectorAll("[data-extra-key]").forEach((element) => {
          addExtraField(element.getAttribute("data-extra-key"), element.getAttribute("data-extra-value"));
          element.remove();
        });
      });
    `;
  }
}

function renderFormFields(template: Record<string, unknown>, disableId: boolean): string {
  const llm = isRecord(template.llm) ? template.llm : {};
  const params = isRecord(llm.params) ? llm.params : {};
  const knownKeys = new Set(["id", "description", "author", "llm", "prompt"]);
  const extraFields = Object.entries(template).filter(([key]) => !knownKeys.has(key));

  return `
    <div class="grid grid-2">
      <div style="grid-column: 1 / -1">
        <label for="prompt-id">ID</label>
        <input id="prompt-id" value="${text(template.id ?? "")}" ${disableId ? "disabled" : ""} />
      </div>
      <div style="grid-column: 1 / -1">
        <label for="prompt-text">Prompt</label>
        <textarea id="prompt-text">${text(template.prompt ?? "")}</textarea>
      </div>
      <div>
        <label for="llm-provider">LLM Provider</label>
        <input id="llm-provider" value="${text(llm.provider ?? "")}" />
      </div>
      <div>
        <label for="llm-model">LLM Model</label>
        <input id="llm-model" value="${text(llm.model ?? "")}" />
      </div>
      <div>
        <label for="description">Description</label>
        <input id="description" value="${text(template.description ?? "")}" />
      </div>
      <div>
        <label for="author">Author</label>
        <input id="author" value="${text(template.author ?? "")}" />
      </div>
      <div>
        <label for="temperature">Temperature</label>
        <input id="temperature" type="number" step="0.01" value="${text(params.temperature ?? "")}" />
      </div>
      <div>
        <label for="max-tokens">Max Tokens</label>
        <input id="max-tokens" type="number" step="1" value="${text(params.max_tokens ?? "")}" />
      </div>
      <div style="grid-column: 1 / -1">
        <label>Extra Fields</label>
        <div id="extra-fields" class="stack"></div>
        ${extraFields
          .map(
            ([key, value]) =>
              `<div data-extra-key="${text(key)}" data-extra-value="${text(String(value ?? ""))}"></div>`,
          )
          .join("")}
        <div class="mt-3"><button class="button button-secondary" data-ui-add-extra="true" type="button">Add Field</button></div>
      </div>
    </div>
    ${renderBumpField()}
  `;
}

function renderBumpField(): string {
  return `
    <div class="stack">
      <label>Bump Level</label>
      <div class="flex wrap">
        <label><input type="radio" name="bump_level" value="patch" checked /> Patch</label>
        <label><input type="radio" name="bump_level" value="minor" /> Minor</label>
        <label><input type="radio" name="bump_level" value="major" /> Major</label>
      </div>
    </div>
  `;
}

function parseBumpLevel(value: unknown): BumpLevel {
  return value === "major" || value === "minor" ? value : "patch";
}

function removeEmptyKeys(template: Record<string, unknown>): void {
  for (const [key, value] of Object.entries(template)) {
    if (value === "") {
      delete template[key];
    }
  }
}

function toYamlString(value: Record<string, unknown>): string {
  return yaml.stringify(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
