from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pvm.core.errors import PVMError
from pvm.project import PVMProject
from pvm.prompts.token_count import count_tokens, list_supported_models


def _write_template(
    path: Path,
    prompt_id: str = "intent_classifier",
    prompt: str = "classify the user intent",
    temperature: float = 0.2,
) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            id: {prompt_id}
            description: description for {prompt_id}
            author: alice
            llm:
              provider: openai
              model: gpt-4.1
              params:
                temperature: {temperature}
                max_tokens: 300
            prompt: |
              {prompt}
            input_variables:
              - user_input
            """
        ),
        encoding="utf-8",
    )


def _make_project_with_prompt(tmp_path: Path) -> tuple[PVMProject, str, str]:
    """Create a project, add a prompt, and return (project, prompt_id, version)."""
    project = PVMProject(tmp_path)
    project.init("test")
    template = tmp_path / "template.yaml"
    _write_template(template, prompt_id="my-prompt", prompt="Hello world, this is a test prompt.")
    result = project.add_prompt(template)
    return project, result["id"], result["version"]


class TestCountTokens:
    def test_returns_positive_count(self, tmp_path: Path) -> None:
        project, prompt_id, version = _make_project_with_prompt(tmp_path)
        result = count_tokens(project.root, prompt_id, version, "gpt-4o")
        assert result["token_count"] > 0
        assert result["id"] == prompt_id
        assert result["version"] == version
        assert result["model"] == "gpt-4o"

    def test_different_models_on_same_prompt(self, tmp_path: Path) -> None:
        project, prompt_id, version = _make_project_with_prompt(tmp_path)
        result_4o = count_tokens(project.root, prompt_id, version, "gpt-4o")
        result_4 = count_tokens(project.root, prompt_id, version, "gpt-4")
        # Both should return positive counts (values may differ by model encoding)
        assert result_4o["token_count"] > 0
        assert result_4["token_count"] > 0

    def test_unsupported_model_raises(self, tmp_path: Path) -> None:
        project, prompt_id, version = _make_project_with_prompt(tmp_path)
        with pytest.raises(PVMError, match="Unsupported model"):
            count_tokens(project.root, prompt_id, version, "totally-fake-model-xyz")


class TestListSupportedModels:
    def test_returns_non_empty_list(self) -> None:
        models = list_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_contains_known_models(self) -> None:
        models = list_supported_models()
        assert "gpt-4o" in models

    def test_list_is_sorted(self) -> None:
        models = list_supported_models()
        assert models == sorted(models)


class TestFacadeMethods:
    def test_count_tokens_via_facade(self, tmp_path: Path) -> None:
        project, prompt_id, version = _make_project_with_prompt(tmp_path)
        result = project.count_tokens(prompt_id, version, "gpt-4o")
        assert result["token_count"] > 0

    def test_list_token_models_via_facade(self, tmp_path: Path) -> None:
        project = PVMProject(tmp_path)
        # list_token_models does not require a valid project
        models = project.list_token_models()
        assert len(models) > 0
        assert "gpt-4o" in models


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())
    return env


def _run_cli(tmp_path: Path, cli_env: dict[str, str], *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pvm.cli", *args],
        cwd=tmp_path, check=check, env=cli_env, capture_output=True, text=True,
    )


class TestCLITokenCount:
    def test_cli_token_count(self, tmp_path: Path, cli_env: dict[str, str]) -> None:
        # init project and add a prompt
        _run_cli(tmp_path, cli_env, "init", "test-project")
        template = tmp_path / "template.yaml"
        _write_template(template, prompt_id="my-prompt", prompt="Hello world, this is a test prompt.")
        add_result = _run_cli(tmp_path, cli_env, "add", str(template))
        add_data = json.loads(add_result.stdout)
        version = add_data["version"]

        # run token-count
        result = _run_cli(tmp_path, cli_env, "token-count", "my-prompt", version, "gpt-4o")
        data = json.loads(result.stdout)
        assert data["id"] == "my-prompt"
        assert data["version"] == version
        assert data["model"] == "gpt-4o"
        assert data["token_count"] > 0

    def test_cli_token_count_list_models(self, tmp_path: Path, cli_env: dict[str, str]) -> None:
        result = _run_cli(tmp_path, cli_env, "token-count", "--list-models")
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert "gpt-4o" in data
