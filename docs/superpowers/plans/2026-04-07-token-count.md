# Token Count Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prompt detail 페이지에서 OpenAI 모델을 선택하면 해당 prompt의 input token 수를 표시한다.

**Architecture:** tiktoken 기반 토큰 계산 함수를 core에 추가하고, CLI `token-count` 명령어로 노출. Local UI는 FastAPI 엔드포인트, VS Code extension은 CLI 호출로 접근.

**Tech Stack:** Python (tiktoken, typer, FastAPI), TypeScript (VS Code extension)

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `pvm/prompts/token_count.py` | Core 토큰 계산 로직 |
| Modify | `pvm/project.py` | Facade에 token_count, list_token_models 메서드 추가 |
| Modify | `pvm/cli.py` | `token-count` CLI 명령어 추가 |
| Modify | `pyproject.toml` | tiktoken 의존성 추가 |
| Modify | `ui/app.py` | Token count API 엔드포인트 추가 |
| Modify | `ui/templates/prompt_detail.html` | 모델 드롭다운 + 토큰 수 표시 UI |
| Modify | `vscode-extension/src/types.ts` | TokenCountResult 타입 추가 |
| Modify | `vscode-extension/src/pvm-cli.ts` | listTokenModels, countTokens 메서드 추가 |
| Modify | `vscode-extension/src/panels/prompt-detail-panel.ts` | 모델 드롭다운 + 토큰 수 표시 |
| Create | `tests/test_token_count.py` | 토큰 계산 테스트 |

---

### Task 1: Add tiktoken dependency

**Files:**
- Modify: `pyproject.toml:11-18`

- [ ] **Step 1: Add tiktoken to dependencies**

```toml
dependencies = [
  "PyYAML>=6.0",
  "typer>=0.12,<1.0",
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "jinja2>=3.1",
  "python-multipart>=0.0.9",
  "tiktoken>=0.8",
]
```

- [ ] **Step 2: Install dependencies**

Run: `poetry lock && poetry install`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "deps: add tiktoken for token counting"
```

---

### Task 2: Core token count module

**Files:**
- Create: `pvm/prompts/token_count.py`
- Create: `tests/test_token_count.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_token_count.py
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pvm.project import PVMProject


def _write_template(
    path: Path,
    prompt_id: str = "test_prompt",
    prompt: str = "classify the user intent",
) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            id: {prompt_id}
            description: test prompt
            author: tester
            llm:
              provider: openai
              model: gpt-4.1
              params:
                temperature: 0.2
                max_tokens: 300
            prompt: |
              {prompt}
            input_variables:
              - user_input
            """
        ),
        encoding="utf-8",
    )


def _make_project(tmp_path: Path) -> PVMProject:
    project = PVMProject(tmp_path)
    project.init("test-project")
    return project


def test_count_tokens_returns_positive_count(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template_path = tmp_path / "template.yaml"
    _write_template(template_path)
    result = project.add_prompt(template_path)

    token_result = project.count_tokens(result["id"], result["version"], "gpt-4o")
    assert token_result["model"] == "gpt-4o"
    assert token_result["token_count"] > 0
    assert token_result["id"] == "test_prompt"
    assert token_result["version"] == result["version"]


def test_count_tokens_different_models_same_prompt(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template_path = tmp_path / "template.yaml"
    _write_template(template_path, prompt="Hello world, this is a test prompt.")
    result = project.add_prompt(template_path)

    r1 = project.count_tokens(result["id"], result["version"], "gpt-4o")
    r2 = project.count_tokens(result["id"], result["version"], "gpt-4o-mini")
    # Both should return positive counts (same tokenizer for these models)
    assert r1["token_count"] > 0
    assert r2["token_count"] > 0


def test_list_token_models_returns_list() -> None:
    from pvm.prompts.token_count import list_supported_models

    models = list_supported_models()
    assert isinstance(models, list)
    assert len(models) > 0
    assert "gpt-4o" in models


def test_count_tokens_unsupported_model(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template_path = tmp_path / "template.yaml"
    _write_template(template_path)
    result = project.add_prompt(template_path)

    with pytest.raises(Exception):
        project.count_tokens(result["id"], result["version"], "nonexistent-model-xyz")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_token_count.py -v`
Expected: FAIL — `count_tokens` method doesn't exist

- [ ] **Step 3: Create core module**

```python
# pvm/prompts/token_count.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import tiktoken

from pvm.core.errors import PVMError
from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists, ensure_prompt_version_exists


def count_tokens(root: Path, prompt_id: str, version: str, model: str) -> dict[str, Any]:
    """Count tokens in a prompt version using the specified model's tokenizer."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)
    ensure_prompt_version_exists(paths, prompt_id, version)

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        raise PVMError(f"Unsupported model for token counting: {model}")

    version_dir = paths.prompt_version_dir(prompt_id, version)
    prompt_text = (version_dir / "prompt.md").read_text(encoding="utf-8")
    token_count = len(encoding.encode(prompt_text))

    return {
        "id": prompt_id,
        "version": version,
        "model": model,
        "token_count": token_count,
    }


def list_supported_models() -> list[str]:
    """Return a sorted list of models that tiktoken supports."""
    from tiktoken import list_models
    return sorted(list_models())
```

Note: `tiktoken.list_models()`가 없을 수 있으므로 구현 시 `tiktoken.model.MODEL_TO_ENCODING` 딕셔너리에서 키를 추출하는 방식으로 fallback 필요. 구현자는 실제 tiktoken API를 확인할 것.

- [ ] **Step 4: Add facade methods to project.py**

`pvm/project.py`에 import 추가 (상단):
```python
from pvm.prompts.token_count import count_tokens as count_prompt_tokens, list_supported_models
```

클래스에 메서드 추가 (`diff_prompt` 메서드 뒤, line 154 이후):
```python
def count_tokens(self, prompt_id: str, version: str, model: str) -> dict[str, Any]:
    """Count tokens in a prompt version using the specified model's tokenizer."""
    self.require_valid()
    return count_prompt_tokens(self.root, prompt_id, version, model)

def list_token_models(self) -> list[str]:
    """List models supported for token counting."""
    return list_supported_models()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/test_token_count.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pvm/prompts/token_count.py pvm/project.py tests/test_token_count.py
git commit -m "feat: add token counting core with tiktoken"
```

---

### Task 3: CLI command

**Files:**
- Modify: `pvm/cli.py:211` (after `log` command)

- [ ] **Step 1: Write CLI test**

`tests/test_token_count.py`에 추가:

```python
import json
import os
import subprocess
import sys


@pytest.fixture
def cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())
    return env


def _run_cli(tmp_path: Path, cli_env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pvm.cli", *args],
        cwd=tmp_path, check=True, env=cli_env, capture_output=True, text=True,
    )


def test_cli_token_count(tmp_path: Path, cli_env: dict[str, str]) -> None:
    _run_cli(tmp_path, cli_env, "init", "test-project")
    template_path = tmp_path / "template.yaml"
    _write_template(template_path)
    output = _run_cli(tmp_path, cli_env, "add", str(template_path))
    result = json.loads(output.stdout)

    output = _run_cli(tmp_path, cli_env, "token-count", result["id"], result["version"], "gpt-4o")
    token_result = json.loads(output.stdout)
    assert token_result["token_count"] > 0
    assert token_result["model"] == "gpt-4o"


def test_cli_token_count_list_models(tmp_path: Path, cli_env: dict[str, str]) -> None:
    output = _run_cli(tmp_path, cli_env, "token-count", "--list-models")
    models = json.loads(output.stdout)
    assert isinstance(models, list)
    assert "gpt-4o" in models
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_token_count.py::test_cli_token_count -v`
Expected: FAIL — command not found

- [ ] **Step 3: Add CLI command**

`pvm/cli.py`에 `log` command 뒤 (line 223 이후)에 추가:

```python
@app.command("token-count")
def token_count(
    prompt_id: str = typer.Argument(None, metavar="ID"),
    version: str = typer.Argument(None),
    model: str = typer.Argument(None),
    list_models: bool = typer.Option(False, "--list-models", help="List supported models"),
) -> None:
    """Count tokens in a prompt version for a specific model."""
    if list_models:
        _print_json(_project().list_token_models())
        return
    if not prompt_id or not version or not model:
        typer.secho("Usage: pvm token-count <ID> <VERSION> <MODEL>", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    _print_json(_project().count_tokens(prompt_id, version, model))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/test_token_count.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pvm/cli.py tests/test_token_count.py
git commit -m "feat: add token-count CLI command"
```

---

### Task 4: Local UI — API endpoints

**Files:**
- Modify: `ui/app.py`

- [ ] **Step 1: Add API endpoints**

`ui/app.py`에 prompt detail 라우트 근처에 추가:

```python
from fastapi.responses import JSONResponse

@app.get("/api/token-count/models")
def token_count_models():
    project = get_project()
    return JSONResponse(content=project.list_token_models())


@app.get("/api/token-count/{prompt_id}/{version}")
def token_count_api(prompt_id: str, version: str, model: str = Query(...)):
    project = get_project()
    return JSONResponse(content=project.count_tokens(prompt_id, version, model))
```

- [ ] **Step 2: Commit**

```bash
git add ui/app.py
git commit -m "feat: add token count API endpoints to local UI"
```

---

### Task 5: Local UI — prompt detail template

**Files:**
- Modify: `ui/templates/prompt_detail.html`

- [ ] **Step 1: Read the current template fully**

Read `ui/templates/prompt_detail.html` to identify the exact insertion point after the LLM CONFIG section.

- [ ] **Step 2: Add token count card**

LLM CONFIG 카드 뒤에 새 카드 추가:

```html
<!-- Token Count -->
<div class="bg-white rounded-lg shadow p-6">
  <h2 class="text-sm font-semibold text-gray-500 mb-3">TOKEN COUNT</h2>
  <div class="space-y-3">
    <div>
      <label class="text-xs text-gray-500">Model</label>
      <select id="token-model-select" class="mt-1 w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-mono">
        <option value="">Select a model...</option>
      </select>
    </div>
    <div id="token-count-result" class="hidden">
      <span class="text-gray-500 text-sm">Input Tokens</span>
      <p id="token-count-value" class="text-2xl font-bold font-mono text-green-600 mt-1"></p>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add JavaScript for AJAX**

페이지 하단에 스크립트 추가:

```html
<script>
  document.addEventListener('DOMContentLoaded', async () => {
    const select = document.getElementById('token-model-select');
    const resultDiv = document.getElementById('token-count-result');
    const valueEl = document.getElementById('token-count-value');

    // Load model list
    const models = await fetch('/api/token-count/models').then(r => r.json());
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      select.appendChild(opt);
    });

    // On model select
    select.addEventListener('change', async () => {
      const model = select.value;
      if (!model) {
        resultDiv.classList.add('hidden');
        return;
      }
      const promptId = '{{ prompt_data.id }}';
      const version = '{{ current_version }}';
      const data = await fetch(`/api/token-count/${promptId}/${version}?model=${model}`).then(r => r.json());
      valueEl.textContent = data.token_count.toLocaleString();
      resultDiv.classList.remove('hidden');
    });
  });
</script>
```

- [ ] **Step 4: Test manually**

Run: `poetry run pvm ui`
Navigate to a prompt detail page, select a model, verify token count appears.

- [ ] **Step 5: Commit**

```bash
git add ui/templates/prompt_detail.html
git commit -m "feat: add token count UI to prompt detail page"
```

---

### Task 6: VS Code Extension — types and CLI wrapper

**Files:**
- Modify: `vscode-extension/src/types.ts`
- Modify: `vscode-extension/src/pvm-cli.ts`

- [ ] **Step 1: Add TokenCountResult type**

`vscode-extension/src/types.ts`에 추가:

```typescript
export interface TokenCountResult {
  id: string;
  version: string;
  model: string;
  token_count: number;
}
```

- [ ] **Step 2: Add PvmCli methods**

`vscode-extension/src/pvm-cli.ts`에 import에 `TokenCountResult` 추가하고, 클래스에 메서드 추가:

```typescript
async listTokenModels(): Promise<string[]> {
  return this.executeJson<string[]>(["token-count", "--list-models"]);
}

async countTokens(promptId: string, version: string, model: string): Promise<TokenCountResult> {
  return this.executeJson<TokenCountResult>(["token-count", promptId, version, model]);
}
```

- [ ] **Step 3: Commit**

```bash
git add vscode-extension/src/types.ts vscode-extension/src/pvm-cli.ts
git commit -m "feat: add token count types and CLI wrapper to extension"
```

---

### Task 7: VS Code Extension — prompt detail panel

**Files:**
- Modify: `vscode-extension/src/panels/prompt-detail-panel.ts`

- [ ] **Step 1: Add token count section to HTML**

`renderPromptContent` 함수 안 (Metadata section 뒤)에 토큰 카운트 카드 추가:

```typescript
function renderTokenCountCard(): string {
  return `
    <section class="card">
      <div class="section-title"><h3>Token Count</h3></div>
      <div class="stack">
        <select id="token-model-select" class="select">
          <option value="">Select a model...</option>
        </select>
        <div id="token-count-result" style="display:none">
          <span class="text-muted text-sm">Input Tokens</span>
          <div id="token-count-value" class="stat-number"></div>
        </div>
      </div>
    </section>
  `;
}
```

- [ ] **Step 2: Load models and handle selection**

`getHtmlContent()`에서 모델 목록을 미리 로드해서 HTML에 포함:

```typescript
const tokenModels = await this.cli.listTokenModels();
```

Select options를 서버사이드로 렌더링:

```typescript
function renderTokenCountCard(models: string[]): string {
  const options = models
    .map((m) => `<option value="${m}">${m}</option>`)
    .join("");
  return `
    <section class="card">
      <div class="section-title"><h3>Token Count</h3></div>
      <div class="stack">
        <select id="token-model-select" class="select">
          <option value="">Select a model...</option>
          ${options}
        </select>
        <div id="token-count-result" style="display:none">
          <span class="text-muted text-sm">Input Tokens</span>
          <div id="token-count-value" class="stat-number"></div>
        </div>
      </div>
    </section>
  `;
}
```

- [ ] **Step 3: Add message handler for token count**

`onMessage`에 케이스 추가:

```typescript
case "tokenCount": {
  const model = String(message.model ?? "");
  if (!model) return;
  const result = await this.cli.countTokens(this.promptId, selectedVersion, model);
  // Send result back to webview
  this.panel?.webview.postMessage({ type: "tokenCountResult", token_count: result.token_count });
  return;
}
```

`getScript()`에 추가:

```javascript
const tokenSelect = document.getElementById('token-model-select');
if (tokenSelect) {
  tokenSelect.addEventListener('change', () => {
    const model = tokenSelect.value;
    if (model) {
      send('tokenCount', { model });
    } else {
      document.getElementById('token-count-result').style.display = 'none';
    }
  });
}

window.addEventListener('message', (event) => {
  const msg = event.data;
  if (msg.type === 'tokenCountResult') {
    const resultDiv = document.getElementById('token-count-result');
    const valueEl = document.getElementById('token-count-value');
    valueEl.textContent = msg.token_count.toLocaleString();
    resultDiv.style.display = 'block';
  }
});
```

- [ ] **Step 4: Build and test**

Run: `cd vscode-extension && node esbuild.js && npx vsce package`
Install `.vsix`, open a prompt detail, select model, verify token count.

- [ ] **Step 5: Commit**

```bash
git add vscode-extension/src/panels/prompt-detail-panel.ts
git commit -m "feat: add token count to extension prompt detail panel"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run all tests**

Run: `poetry run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Test local UI end-to-end**

Run: `poetry run pvm ui`
1. Navigate to prompt detail
2. Select model from dropdown
3. Verify token count displays

- [ ] **Step 3: Test VS Code extension end-to-end**

1. Install fresh `.vsix`
2. Open prompt detail
3. Select model
4. Verify token count displays

- [ ] **Step 4: Final commit if needed**

```bash
git add -A
git commit -m "feat: token count feature complete"
```
