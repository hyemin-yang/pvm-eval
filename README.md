# pvm

`pvm` is a local prompt version management tool.

It manages:

- prompt versions per `id`
- production pointers per prompt
- prompt diffs
- production snapshots
- a Typer-based CLI on top of the Python library

## Install

### Recommended: `pipx`

Use `pipx` if you want `pvm` available like `git`.

Install from a local checkout:

```bash
pipx install /path/to/pvm
```

Install from GitHub:

```bash
pipx install "git+https://github.com/OWNER/REPO.git@main"
```

Upgrade after changes:

```bash
pipx reinstall pvm
```

If you publish version bumps, `pipx upgrade pvm` works as well.

### Local development with Poetry

```bash
poetry install -E dev
poetry run pvm --help
```

### Build a distributable package

```bash
poetry build
```

This creates:

- `dist/pvm-0.0.0-py3-none-any.whl`
- `dist/pvm-0.0.0.tar.gz`

You can install the wheel with:

```bash
pipx install dist/pvm-0.0.0-py3-none-any.whl
```

## Quick Start

Initialize a project in the current directory. If `name` is omitted, `my-project` is used.

```bash
pvm init
```

Print the default prompt template:

```bash
pvm template
```

Save a prompt YAML file and add it:

```bash
pvm add prompt.yaml
```

Minor and major bumps are supported:

```bash
pvm add prompt.yaml --minor
pvm add prompt.yaml --major
```

Deploy the latest version for a prompt:

```bash
pvm deploy intent_classifier
```

Deploy a specific version:

```bash
pvm deploy intent_classifier 0.1.0
```

Read a prompt:

```bash
pvm get intent_classifier
pvm get intent_classifier --version 0.1.0
```

Create snapshots:

```bash
pvm snapshot create
pvm snapshot create --minor
pvm snapshot create --major
```

Inspect the project summary:

```bash
pvm project
```

## Prompt Template

The default YAML template is:

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

Required fields:

- `id`
- `llm`
- `prompt`

Rules:

- `id` is the stable prompt identifier
- `id` cannot contain spaces or `/`
- the first version is always `0.1.0`
- identical content is a no-op

## Project Layout

After `pvm init`, the project contains a local `.pvm/` directory.

```text
.pvm/
  config.yaml
  settings/
    template.yaml
  prompts/
    {id}/
      info.yaml
      production.json
      history.jsonl
      versions/
        {version}/
          prompt.md
          model_config.json
          metadata.json
          template.yaml
  snapshots/
    history.jsonl
    versions/
      {version}.json
```

## Current Command Set

Top-level commands:

- `pvm init [name]`
- `pvm add <file> [--minor|--major]`
- `pvm deploy <id> [version]`
- `pvm rollback <id>`
- `pvm get <id> [--version <version>]`
- `pvm diff <id> <from_version> <to_version>`
- `pvm list [--id <id>]`
- `pvm id <id> [--info] [--list]`
- `pvm log [--id <id>]`
- `pvm project`
- `pvm template`

Snapshot commands:

- `pvm snapshot create [--minor|--major]`
- `pvm snapshot list`
- `pvm snapshot get <version>`
- `pvm snapshot read <version>`
- `pvm snapshot diff <from_version> <to_version>`

Detailed CLI examples are in `docs/CLI.md`.

Additional documents:

- Korean README: `docs/README_KO.md`
- Korean CLI guide: `docs/CLI_KO.md`
- Design: `docs/DESIGN.md`
- Implementation status: `docs/IMPLEMENTATION_TODO.md`

## Command Behavior Notes

- `pvm init` defaults the project name to `my-project`
- `pvm add` defaults to a patch bump; `--minor` and `--major` are mutually exclusive
- the first prompt version is always `0.1.0`
- `pvm deploy <id>` deploys the latest version if `version` is omitted
- redeploying the current production version is a no-op
- `pvm get <id>` returns production if it exists, otherwise the latest version
- `pvm get <id> --version <version>` is strict and errors if that version does not exist
- the first snapshot version is always `0.1.0`
- `pvm project` shows the project, prompt ids, prompt versions, production markers, and snapshot versions

## Testing

Run the test suite with Poetry:

```bash
poetry run python -m pytest -q
```
