# pvm

`pvm` is a prompt version management tool for projects that store prompt artifacts in a local `.pvm/` directory.

It manages:

- prompt versions per `id`
- production pointers per prompt
- prompt diffs
- production snapshots
- a CLI on top of the Python library

## Install

### Recommended: `pipx`

If you want to use `pvm` like `git` from any directory, install it as a global CLI with `pipx`.

From this repository:

```bash
pipx install /path/to/pvm
```

After installation:

```bash
pvm --help
```

### Local development with Poetry

```bash
poetry install -E dev
poetry run pvm --help
```

### Build a distributable package

```bash
poetry build
```

This produces:

- `dist/pvm-0.1.0-py3-none-any.whl`
- `dist/pvm-0.1.0.tar.gz`

You can then install the wheel in another environment:

```bash
pipx install dist/pvm-0.1.0-py3-none-any.whl
```

## Quick Start

Initialize a project in the current directory:

```bash
pvm init my-project
```

Print the default prompt template:

```bash
pvm template
```

Add a prompt YAML file:

```bash
pvm add prompt.yaml
```

List prompt ids:

```bash
pvm list
```

List versions for a single prompt:

```bash
pvm list --id intent_classifier
```

Deploy a prompt version:

```bash
pvm deploy intent_classifier 0.1.0
```

Read the current production prompt:

```bash
pvm get intent_classifier
```

Diff two prompt versions:

```bash
pvm diff intent_classifier 0.1.0 0.1.1
```

Create and inspect snapshots:

```bash
pvm snapshot create
pvm snapshot list
pvm snapshot get 0.1.0
pvm snapshot read 0.1.0
pvm snapshot diff 0.1.0 0.1.1
```

## Project Layout

After `pvm init`, the project contains a local `.pvm/` directory.

```text
.pvm/
  config.yaml
  settings/
    template.yaml
  prompts/
  snapshots/
    history.jsonl
    versions/
```

## CLI Commands

Available top-level commands:

- `pvm init`
- `pvm add`
- `pvm deploy`
- `pvm rollback`
- `pvm get`
- `pvm diff`
- `pvm list`
- `pvm id`
- `pvm log`
- `pvm tree`
- `pvm template`
- `pvm snapshot ...`

## Testing

Run the test suite with Poetry:

```bash
poetry run python -m pytest -q
```
