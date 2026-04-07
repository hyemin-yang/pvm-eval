export type BumpLevel = "patch" | "minor" | "major";

export interface PromptAddResult {
  id: string;
  version: string;
  changed: boolean;
  reason?: string;
}

export interface DeployResult {
  id: string;
  version: string | null;
  changed: boolean;
  reason?: string;
  from_version?: string | null;
}

export interface RollbackResult {
  id: string;
  changed: boolean;
  reason?: string;
  from_version?: string;
  to_version?: string;
}

export interface PromptMetadata {
  id: string;
  version: string;
  description: string;
  author: string;
  created_at: string;
  source_file: string;
  prompt_checksum: string;
  model_config_checksum: string;
  template_checksum: string;
}

export interface PromptGetResult {
  id: string;
  version: string;
  llm: Record<string, unknown>;
  prompt: string;
  metadata: PromptMetadata;
}

export interface ProductionInfo {
  id: string;
  version: string;
  previous_versions: string[];
  updated_at: string;
}

export interface PromptStableInfo {
  id: string;
  description: string;
  author: string;
  created_at: string;
}

export interface PromptInfoResult {
  id: string;
  info: PromptStableInfo;
  versions: string[];
  latest_version: string | null;
  production: ProductionInfo | null;
}

export interface PromptSummary extends PromptInfoResult {}

export interface PromptDiffResult {
  id: string;
  from_version: string;
  to_version: string;
  changed: boolean;
  prompt_length_delta: number;
  lines_added: number;
  lines_removed: number;
  model_config_changed: boolean;
  checksum_from: string;
  checksum_to: string;
  unified_diff: string;
}

export interface SnapshotPromptEntry {
  version: string;
  prompt_checksum: string;
  model_config_checksum: string;
}

export interface SnapshotManifest {
  version: string;
  created_at: string;
  snapshot_checksum: string;
  prompt_count: number;
  prompts: Record<string, SnapshotPromptEntry>;
}

export interface SnapshotReadResult {
  version: string;
  created_at: string;
  prompt_count: number;
  prompts: Record<string, PromptGetResult>;
}

export interface SnapshotDiffChange {
  id: string;
  from_version: string;
  to_version: string;
}

export interface SnapshotDiffResult {
  from_version: string;
  to_version: string;
  added_ids: string[];
  removed_ids: string[];
  changed_ids: SnapshotDiffChange[];
}

export interface DeleteResult {
  id: string;
  deleted: boolean;
}

export interface InitResult {
  project_id: string;
  name: string;
  created_at: string;
  root: string;
}

export interface IntegrityResult {
  valid: boolean;
  missing_dirs: string[];
  missing_files: string[];
}

export interface ProjectConfig {
  project_id: string;
  name: string;
  created_at: string;
}

export interface HistoryEntry {
  ts: string;
  event: string;
  id?: string;
  version?: string;
  from_version?: string | null;
  to_version?: string;
  prompt_count?: number;
  template_checksum?: string;
}

export interface TokenCountResult {
  id: string;
  version: string;
  model: string;
  token_count: number;
}
