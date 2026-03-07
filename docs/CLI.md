# CLI Usage

## Overview

`pvm` is a project-local CLI.

Most commands must be run inside a directory that already contains `.pvm/`.

## Initialization

Create a project:

```bash
pvm init
```

Create a project with an explicit name:

```bash
pvm init my-project
```

Print the default YAML template:

```bash
pvm template
```

To create a new template file directly:

```bash
pvm template > prompt.yaml
```

The default output looks like this:

```yaml
id: "intent_classifier"
description: "Classify the user's intent"
author: "alice"

llm:
  provider: "openai"
  model: "gpt-4.1"
  params:
    temperature: 0.2
    max_tokens: 300

prompt: |
  Classify the user's intent.

input_variables:
  - user_input
  - history
```

## Prompt Commands

### `pvm add`

Add a prompt template and create a new immutable version:

```bash
pvm add prompt.yaml
```

Minor or major bump:

```bash
pvm add prompt.yaml --minor
pvm add prompt.yaml --major
```

Rules:

- default bump is patch
- `--minor` and `--major` cannot be used together
- first version is always `0.1.0`
- identical content returns `No changes`

### `pvm list`

List prompt ids:

```bash
pvm list
```

List versions for one prompt:

```bash
pvm list --id intent_classifier
```

### `pvm get`

Read a prompt:

```bash
pvm get intent_classifier
```

Explicit version:

```bash
pvm get intent_classifier --version 0.1.0
```

Resolution rules:

- explicit `--version`: return that version or error
- no `--version` and production exists: return production
- no `--version` and production does not exist: return latest version

### `pvm deploy`

Deploy the latest version:

```bash
pvm deploy intent_classifier
```

Deploy an explicit version:

```bash
pvm deploy intent_classifier 0.1.1
```

Behavior:

- omitted `version` means latest version
- missing version prints `Version not found`
- deploying the already active production version prints `Already deployed to production`

### `pvm rollback`

Rollback to the previous production version:

```bash
pvm rollback intent_classifier
```

If no rollback target exists, the CLI prints `No rollback target`.

### `pvm diff`

Compare two prompt versions:

```bash
pvm diff intent_classifier 0.1.0 0.1.1
```

The JSON output includes:

- `changed`
- `prompt_length_delta`
- `lines_added`
- `lines_removed`
- `model_config_changed`
- `checksum_from`
- `checksum_to`
- `unified_diff`

`unified_diff` is the main field for reading the actual text change.

## Project Summary

Show the current project summary:

```bash
pvm project
```

Example:

```text
project: demo-project
├── id: intent_classifier
│   ├── version: 0.1.0
│   └── version: 0.1.1 <--- production
└── snapshot: 0.1.0
```

## Metadata and History

Inspect a single prompt id:

```bash
pvm id intent_classifier
pvm id intent_classifier --info
pvm id intent_classifier --list
```

Read history logs:

```bash
pvm log
pvm log --id intent_classifier
```

## Snapshot Commands

### `pvm snapshot create`

Create a production snapshot:

```bash
pvm snapshot create
```

Minor or major bump:

```bash
pvm snapshot create --minor
pvm snapshot create --major
```

Rules:

- default bump is patch
- `--minor` and `--major` cannot be used together
- first snapshot version is always `0.1.0`

### `pvm snapshot list`

```bash
pvm snapshot list
```

### `pvm snapshot get`

Read the stored snapshot manifest:

```bash
pvm snapshot get 0.1.0
```

### `pvm snapshot read`

Read the expanded prompt contents for a snapshot:

```bash
pvm snapshot read 0.1.0
```

### `pvm snapshot diff`

Compare two snapshots:

```bash
pvm snapshot diff 0.1.1 0.1.2
```

The JSON output includes:

- `added_ids`
- `removed_ids`
- `changed_ids`

`changed_ids` shows prompt ids whose production version mapping changed between the two snapshots.

## Errors

Expected CLI errors do not print Python tracebacks.

Examples:

- invalid project directory
- missing explicit prompt version
- invalid semantic version input such as `0.1.0-alpha`
- mutually exclusive bump options

## Help

```bash
pvm --help
pvm snapshot --help
```
