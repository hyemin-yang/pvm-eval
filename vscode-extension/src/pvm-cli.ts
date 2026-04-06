import * as cp from "node:child_process";
import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as yaml from "yaml";

import type {
  BumpLevel,
  DeleteResult,
  DeployResult,
  HistoryEntry,
  InitResult,
  IntegrityResult,
  ProjectConfig,
  PromptAddResult,
  PromptDiffResult,
  PromptGetResult,
  PromptInfoResult,
  PromptSummary,
  RollbackResult,
  SnapshotDiffResult,
  SnapshotManifest,
  SnapshotReadResult,
} from "./types";

type CommandCandidate = {
  key: "poetry" | "python" | "py";
  command: string;
  args: string[];
};

export class PvmCli {
  private readonly readCache = new Map<string, Promise<unknown>>();
  private preferredCandidateKey?: CommandCandidate["key"];

  constructor(private readonly workspaceRoot: string) {}

  async checkIntegrity(): Promise<IntegrityResult> {
    return this.cachedRead("integrity", async () => {
      const requiredDirs = [
        ".pvm",
        ".pvm/settings",
        ".pvm/prompts",
        ".pvm/snapshots",
        ".pvm/snapshots/versions",
      ];
      const requiredFiles = [
        ".pvm/config.yaml",
        ".pvm/settings/template.yaml",
        ".pvm/snapshots/history.jsonl",
      ];

      const missing_dirs = requiredDirs.filter((entry) => !isDirectory(path.join(this.workspaceRoot, entry)));
      const missing_files = requiredFiles.filter((entry) => !isFile(path.join(this.workspaceRoot, entry)));

      return {
        valid: missing_dirs.length === 0 && missing_files.length === 0,
        missing_dirs,
        missing_files,
      };
    });
  }

  async isProjectValid(): Promise<boolean> {
    const integrity = await this.checkIntegrity();
    return integrity.valid;
  }

  async init(name: string): Promise<InitResult> {
    const result = await this.executeJson<InitResult>(["init", name]);
    this.invalidateReads();
    return result;
  }

  async destroy(): Promise<void> {
    await this.execute(["destroy", "--force"]);
    this.invalidateReads();
  }

  async destroyProjectDirectory(): Promise<void> {
    await fs.rm(path.join(this.workspaceRoot, ".pvm"), { recursive: true, force: true });
    this.invalidateReads();
  }

  async reset(): Promise<void> {
    await this.execute(["reset", "--force"]);
    this.invalidateReads();
  }

  async project(): Promise<string> {
    return this.cachedRead("project-tree", async () => {
      const config = await this.loadProjectConfig();
      const promptSummaries = await this.getPromptSummaries();
      const snapshots = await this.listSnapshots();
      if (!config) {
        return "project: unknown";
      }
      if (promptSummaries.length === 0 && snapshots.length === 0) {
        return `project: ${config.name}`;
      }

      const lines = [`project: ${config.name}`];
      for (const summary of promptSummaries) {
        lines.push(`|- id: ${summary.id}`);
        for (const version of summary.versions) {
          const suffix = summary.production?.version === version ? " <--- production" : "";
          lines.push(`|  |- version: ${version}${suffix}`);
        }
      }
      for (const version of snapshots) {
        lines.push(`|- snapshot: ${version}`);
      }
      return lines.join("\n");
    });
  }

  async listPromptIds(): Promise<string[]> {
    return this.cachedRead("prompt-ids", async () => {
      const promptsDir = path.join(this.workspaceRoot, ".pvm", "prompts");
      const entries = await listDirectories(promptsDir);
      return entries.sort();
    });
  }

  async listPromptVersions(promptId: string): Promise<string[]> {
    return this.cachedRead(`prompt-versions:${promptId}`, () =>
      listDirectories(path.join(this.workspaceRoot, ".pvm", "prompts", promptId, "versions")).then((versions) =>
        versions.sort(compareSemver),
      ),
    );
  }

  async getPrompt(promptId: string, version?: string): Promise<PromptGetResult> {
    return this.cachedRead(`prompt:${promptId}:${version ?? "current"}`, async () => {
      const info = await this.getPromptInfo(promptId);
      const targetVersion = version ?? info.production?.version ?? info.latest_version;
      if (!targetVersion) {
        throw new Error(`No versions exist for prompt: ${promptId}`);
      }
      const versionDir = path.join(this.workspaceRoot, ".pvm", "prompts", promptId, "versions", targetVersion);
      return {
        id: promptId,
        version: targetVersion,
        llm: await readJson(path.join(versionDir, "model_config.json")),
        prompt: await fs.readFile(path.join(versionDir, "prompt.md"), "utf8"),
        metadata: await readJson(path.join(versionDir, "metadata.json")),
      } as PromptGetResult;
    });
  }

  async getPromptInfo(promptId: string): Promise<PromptInfoResult> {
    return this.cachedRead(`prompt-info:${promptId}`, () =>
      (async () => {
        const promptDir = path.join(this.workspaceRoot, ".pvm", "prompts", promptId);
        if (!isDirectory(promptDir)) {
          throw new Error(`Prompt not found: ${promptId}`);
        }
        const versions = await this.listPromptVersions(promptId);
        const productionPath = path.join(promptDir, "production.json");
        return {
          id: promptId,
          info: toPromptStableInfo(await readYaml(path.join(promptDir, "info.yaml"))),
          versions,
          latest_version: versions.at(-1) ?? null,
          production: isFile(productionPath) ? ((await readJson(productionPath)) as PromptInfoResult["production"]) : null,
        };
      })(),
    );
  }

  async getPromptSummaries(): Promise<PromptSummary[]> {
    return this.cachedRead("prompt-summaries", async () => {
      const ids = await this.listPromptIds();
      const infos = await Promise.all(ids.map((promptId) => this.getPromptInfo(promptId)));
      return infos.sort((left, right) => left.id.localeCompare(right.id));
    });
  }

  async addTemplateFile(templatePath: string, bumpLevel: BumpLevel = "patch"): Promise<PromptAddResult> {
    const args = ["add", templatePath];
    if (bumpLevel !== "patch") {
      args.push(`--${bumpLevel}`);
    }
    const result = await this.executeJson<PromptAddResult>(args);
    this.invalidateReads();
    return result;
  }

  async addTemplateContent(content: string, bumpLevel: BumpLevel = "patch"): Promise<PromptAddResult> {
    return this.withTempYamlFile(content, (templatePath) => this.addTemplateFile(templatePath, bumpLevel));
  }

  async addTemplateObject(template: Record<string, unknown>, bumpLevel: BumpLevel = "patch"): Promise<PromptAddResult> {
    return this.addTemplateContent(yaml.stringify(template), bumpLevel);
  }

  async deploy(promptId: string, version?: string): Promise<DeployResult> {
    const args = ["deploy", promptId];
    if (version) {
      args.push(version);
    }
    const result = await this.executeJson<DeployResult>(args);
    this.invalidateReads();
    return result;
  }

  async rollback(promptId: string): Promise<RollbackResult> {
    const output = await this.execute(["rollback", promptId]);
    if (output.trim() === "No rollback target") {
      return {
        id: promptId,
        changed: false,
        reason: "no_rollback_target",
      };
    }
    const result = JSON.parse(output) as RollbackResult;
    this.invalidateReads();
    return result;
  }

  async deletePrompt(promptId: string): Promise<DeleteResult> {
    const result = await this.executeJson<DeleteResult>(["delete", promptId, "--force"]);
    this.invalidateReads();
    return result;
  }

  async diffPrompt(promptId: string, fromVersion: string, toVersion: string): Promise<PromptDiffResult> {
    return this.executeJson<PromptDiffResult>(["diff", promptId, fromVersion, toVersion]);
  }

  async listSnapshots(): Promise<string[]> {
    return this.cachedRead("snapshots", async () => {
      const versionsDir = path.join(this.workspaceRoot, ".pvm", "snapshots", "versions");
      const versions = await listDirectories(versionsDir);
      return versions.sort(compareSemver);
    });
  }

  async getSnapshot(version: string): Promise<SnapshotManifest> {
    return this.cachedRead(`snapshot:${version}`, () =>
      readJson(path.join(this.workspaceRoot, ".pvm", "snapshots", "versions", version, "manifest.json")) as Promise<SnapshotManifest>,
    );
  }

  async getSnapshotSummaries(): Promise<SnapshotManifest[]> {
    return this.cachedRead("snapshot-summaries", async () => {
      const versions = await this.listSnapshots();
      return Promise.all(versions.map((version) => this.getSnapshot(version)));
    });
  }

  async readSnapshot(version: string): Promise<SnapshotReadResult> {
    return this.cachedRead(`snapshot-read:${version}`, () =>
      (async () => {
        const manifest = await this.getSnapshot(version);
        const prompts = Object.fromEntries(
          await Promise.all(
            Object.entries(manifest.prompts).map(async ([promptId, promptInfo]) => {
              const promptDir = path.join(this.workspaceRoot, ".pvm", "snapshots", "versions", version, "prompts", promptId);
              return [
                promptId,
                {
                  version: promptInfo.version,
                  llm: await readJson(path.join(promptDir, "model_config.json")),
                  prompt: await fs.readFile(path.join(promptDir, "prompt.md"), "utf8"),
                  metadata: await readJson(path.join(promptDir, "metadata.json")),
                },
              ];
            }),
          ),
        );
        return {
          version: manifest.version,
          created_at: manifest.created_at,
          prompt_count: manifest.prompt_count,
          prompts,
        } as SnapshotReadResult;
      })(),
    );
  }

  async createSnapshot(bumpLevel: BumpLevel = "patch"): Promise<SnapshotManifest> {
    const args = ["snapshot", "create"];
    if (bumpLevel !== "patch") {
      args.push(`--${bumpLevel}`);
    }
    const result = await this.executeJson<SnapshotManifest>(args);
    this.invalidateReads();
    return result;
  }

  async exportSnapshot(version: string, outputPath?: string): Promise<{ version: string; output_path: string }> {
    const args = ["snapshot", "export", version];
    if (outputPath) {
      args.push("--output", outputPath);
    }
    return this.executeJson<{ version: string; output_path: string }>(args);
  }

  async diffSnapshot(fromVersion: string, toVersion: string): Promise<SnapshotDiffResult> {
    return this.executeJson<SnapshotDiffResult>(["snapshot", "diff", fromVersion, toVersion]);
  }

  async readHistory(promptId?: string): Promise<HistoryEntry[]> {
    return this.cachedRead(`history:${promptId ?? "snapshots"}`, async () => {
      const historyPath = promptId
        ? path.join(this.workspaceRoot, ".pvm", "prompts", promptId, "history.jsonl")
        : path.join(this.workspaceRoot, ".pvm", "snapshots", "history.jsonl");
      if (!isFile(historyPath)) {
        return [];
      }
      const output = await fs.readFile(historyPath, "utf8");
      const trimmed = output.trim();
      if (!trimmed || trimmed === "[]") {
        return [];
      }
      return trimmed
        .split(/\r?\n/)
        .filter(Boolean)
        .map((line) => JSON.parse(line) as HistoryEntry);
    });
  }

  async loadProjectConfig(): Promise<ProjectConfig | null> {
    return this.cachedRead("project-config", async () => {
      const configPath = path.join(this.workspaceRoot, ".pvm", "config.yaml");
      try {
        const text = await fs.readFile(configPath, "utf8");
        return yaml.parse(text) as ProjectConfig;
      } catch {
        return null;
      }
    });
  }

  async loadDefaultTemplate(): Promise<Record<string, unknown>> {
    return this.cachedRead("default-template", async () => {
      const templatePath = path.join(this.workspaceRoot, ".pvm", "settings", "template.yaml");
      const text = await fs.readFile(templatePath, "utf8");
      return (yaml.parse(text) ?? {}) as Record<string, unknown>;
    });
  }

  async loadPromptTemplate(promptId: string, version?: string): Promise<Record<string, unknown>> {
    return this.cachedRead(`prompt-template:${promptId}:${version ?? "latest"}`, async () => {
      const resolvedVersion = version ?? (await this.getPromptInfo(promptId)).latest_version;
      if (!resolvedVersion) {
        return {};
      }
      const templatePath = path.join(
        this.workspaceRoot,
        ".pvm",
        "prompts",
        promptId,
        "versions",
        resolvedVersion,
        "template.yaml",
      );
      const text = await fs.readFile(templatePath, "utf8");
      return (yaml.parse(text) ?? {}) as Record<string, unknown>;
    });
  }

  getWorkspaceRoot(): string {
    return this.workspaceRoot;
  }

  private async executeJson<T>(args: string[]): Promise<T> {
    const output = await this.execute(args);
    return JSON.parse(output) as T;
  }

  private async execute(args: string[]): Promise<string> {
    const candidates = this.getCommandCandidates(args);

    let lastMissingError: Error | undefined;

    for (const candidate of candidates) {
      try {
        return await this.runCandidate(candidate);
      } catch (error) {
        if (isMissingExecutable(error)) {
          lastMissingError = error instanceof Error ? error : new Error(String(error));
          continue;
        }
        throw error;
      }
    }

    throw lastMissingError ?? new Error("Unable to execute pvm CLI.");
  }

  private runCandidate(candidate: CommandCandidate): Promise<string> {
    return new Promise((resolve, reject) => {
      cp.execFile(
        candidate.command,
        candidate.args,
        {
          cwd: this.workspaceRoot,
          windowsHide: true,
          maxBuffer: 10 * 1024 * 1024,
        },
        (error, stdout, stderr) => {
          if (error) {
            const message = (stderr || error.message).trim() || error.message;
            reject(new Error(message));
            return;
          }
          this.preferredCandidateKey = candidate.key;
          resolve(stdout.trim());
        },
      );
    });
  }

  private getCommandCandidates(args: string[]): CommandCandidate[] {
    const baseCandidates: CommandCandidate[] = [
      { key: "poetry", command: "poetry", args: ["run", "pvm", ...args] },
      { key: "python", command: "python", args: ["-m", "pvm.cli", ...args] },
      { key: "py", command: "py", args: ["-m", "pvm.cli", ...args] },
    ];

    if (!this.preferredCandidateKey) {
      return baseCandidates;
    }

    return [
      ...baseCandidates.filter((candidate) => candidate.key === this.preferredCandidateKey),
      ...baseCandidates.filter((candidate) => candidate.key !== this.preferredCandidateKey),
    ];
  }

  private cachedRead<T>(key: string, load: () => Promise<T>): Promise<T> {
    const cached = this.readCache.get(key) as Promise<T> | undefined;
    if (cached) {
      return cached;
    }

    const pending = load().catch((error) => {
      this.readCache.delete(key);
      throw error;
    });
    this.readCache.set(key, pending);
    return pending;
  }

  private invalidateReads(): void {
    this.readCache.clear();
  }

  private async withTempYamlFile<T>(content: string, fn: (templatePath: string) => Promise<T>): Promise<T> {
    const tempPath = path.join(os.tmpdir(), `pvm-${Date.now()}-${Math.random().toString(16).slice(2)}.yaml`);
    await fs.writeFile(tempPath, content, "utf8");
    try {
      return await fn(tempPath);
    } finally {
      await fs.rm(tempPath, { force: true });
    }
  }
}

function isMissingExecutable(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.message.includes("ENOENT") || error.message.includes("not recognized");
}

async function listDirectories(dirPath: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  } catch {
    return [];
  }
}

async function readJson(filePath: string): Promise<any> {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

async function readYaml(filePath: string): Promise<Record<string, unknown>> {
  return (yaml.parse(await fs.readFile(filePath, "utf8")) ?? {}) as Record<string, unknown>;
}

function isDirectory(filePath: string): boolean {
  try {
    return fsSync.statSync(filePath).isDirectory();
  } catch {
    return false;
  }
}

function isFile(filePath: string): boolean {
  try {
    return fsSync.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function compareSemver(left: string, right: string): number {
  const leftParts = left.split(".").map((part) => Number(part));
  const rightParts = right.split(".").map((part) => Number(part));
  for (let index = 0; index < 3; index += 1) {
    const diff = (leftParts[index] ?? 0) - (rightParts[index] ?? 0);
    if (diff !== 0) {
      return diff;
    }
  }
  return 0;
}

function toPromptStableInfo(value: Record<string, unknown>): PromptInfoResult["info"] {
  return {
    id: String(value.id ?? ""),
    description: String(value.description ?? ""),
    author: String(value.author ?? ""),
    created_at: String(value.created_at ?? ""),
  };
}
