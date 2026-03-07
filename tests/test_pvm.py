from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pvm.core.errors import AlreadyInitializedError, NotValidProjectError
from pvm.project import PVMProject


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


def _make_project(tmp_path: Path) -> PVMProject:
    project = PVMProject(tmp_path)
    project.init("demo-project")
    return project


def test_init_creates_valid_project(tmp_path: Path) -> None:
    project = PVMProject(tmp_path)
    result = project.init("demo-project")

    assert project.is_valid() is True
    assert result["name"] == "demo-project"
    assert (tmp_path / ".pvm" / "config.yaml").exists()


def test_init_uses_default_name(tmp_path: Path) -> None:
    project = PVMProject(tmp_path)
    result = project.init()

    assert project.is_valid() is True
    assert result["name"] == "my-project"
    assert project.load_config()["name"] == "my-project"


def test_invalid_project_raises(tmp_path: Path) -> None:
    project = PVMProject(tmp_path)
    assert project.is_valid() is False

    with pytest.raises(NotValidProjectError):
        project.require_valid()


def test_init_twice_raises(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    with pytest.raises(AlreadyInitializedError):
        project.init("demo-project")


def test_add_first_version(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)

    result = project.add_prompt(template)

    assert result == {"id": "intent_classifier", "version": "0.1.0", "changed": True}
    assert (tmp_path / ".pvm" / "prompts" / "intent_classifier" / "versions" / "0.1.0" / "prompt.md").exists()


def test_add_patch_increment(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    _write_template(template, prompt="classify the user intent carefully", temperature=0.3)
    result = project.add_prompt(template)

    assert result["version"] == "0.1.1"


def test_add_noop_on_identical_content(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    result = project.add_prompt(template)

    assert result["changed"] is False
    assert result["reason"] == "no_changes"


def test_deploy_and_get_production(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    deploy_result = project.deploy("intent_classifier", "0.1.0")
    prompt = project.get_prompt("intent_classifier")

    assert deploy_result["changed"] is True
    assert prompt["version"] == "0.1.0"


def test_deploy_without_version_uses_latest(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    _write_template(template, prompt="classify carefully", temperature=0.3)
    project.add_prompt(template)

    deploy_result = project.deploy("intent_classifier")

    assert deploy_result["changed"] is True
    assert deploy_result["version"] == "0.1.1"
    assert project.get_prompt("intent_classifier")["version"] == "0.1.1"


def test_deploy_same_version_is_noop(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    first = project.deploy("intent_classifier", "0.1.0")
    second = project.deploy("intent_classifier", "0.1.0")

    assert first["changed"] is True
    assert second["changed"] is False
    assert second["reason"] == "already_deployed"


def test_rollback_to_previous_version(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    _write_template(template, prompt="classify carefully", temperature=0.3)
    project.add_prompt(template)

    project.deploy("intent_classifier", "0.1.0")
    project.deploy("intent_classifier", "0.1.1")

    rollback_result = project.rollback("intent_classifier")

    assert rollback_result["changed"] is True
    assert rollback_result["to_version"] == "0.1.0"
    assert project.get_prompt("intent_classifier")["version"] == "0.1.0"


def test_prompt_diff(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template = tmp_path / "prompt.yaml"
    _write_template(template)
    project.add_prompt(template)

    _write_template(template, prompt="classify carefully", temperature=0.3)
    project.add_prompt(template)

    diff = project.diff_prompt("intent_classifier", "0.1.0", "0.1.1")

    assert diff["changed"] is True
    assert diff["model_config_changed"] is True
    assert "prompt.md" in diff["unified_diff"]


def test_snapshot_create_get_read_and_diff(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    template_a = tmp_path / "prompt_a.yaml"
    template_b = tmp_path / "prompt_b.yaml"

    _write_template(template_a, prompt_id="intent_classifier", prompt="classify the user intent")
    _write_template(template_b, prompt_id="planner", prompt="plan the next action", temperature=0.1)

    project.add_prompt(template_a)
    project.add_prompt(template_b)
    project.deploy("intent_classifier", "0.1.0")
    project.deploy("planner", "0.1.0")
    snapshot_a = project.create_snapshot()

    _write_template(template_a, prompt_id="intent_classifier", prompt="classify carefully", temperature=0.3)
    project.add_prompt(template_a)
    project.deploy("intent_classifier", "0.1.1")
    snapshot_b = project.create_snapshot()

    snapshot_versions = project.list_snapshots()
    manifest = project.get_snapshot(snapshot_a["version"])
    expanded = project.read_snapshot(snapshot_b["version"])
    diff = project.diff_snapshot(snapshot_a["version"], snapshot_b["version"])

    assert snapshot_versions == ["0.1.0", "0.1.1"]
    assert manifest["prompt_count"] == 2
    assert expanded["prompts"]["intent_classifier"]["version"] == "0.1.1"
    assert diff["changed_ids"] == [
        {"id": "intent_classifier", "from_version": "0.1.0", "to_version": "0.1.1"}
    ]


def test_cli_init_and_list(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init", "demo-project"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "list"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def test_cli_init_uses_default_name(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["name"] == "my-project"


def test_cli_template(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init", "demo-project"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "template"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "id: intent_classifier" in result.stdout
    assert "llm:" in result.stdout


def test_cli_deploy_without_version_uses_latest(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init", "demo-project"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    template = tmp_path / "prompt.yaml"
    _write_template(template)
    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "add", str(template)],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    _write_template(template, prompt="classify carefully", temperature=0.3)
    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "add", str(template)],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "deploy", "intent_classifier"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["version"] == "0.1.1"


def test_cli_deploy_same_version_is_noop(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init", "demo-project"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    template = tmp_path / "prompt.yaml"
    _write_template(template)
    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "add", str(template)],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "deploy", "intent_classifier", "0.1.0"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "deploy", "intent_classifier", "0.1.0"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "Already deployed to production"


def test_cli_hides_traceback_for_domain_errors(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "list"],
        cwd=tmp_path,
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "not a valid pvm project" in result.stderr


def test_cli_tree_shows_project_name_only_when_empty(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "tree"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "my-project"


def test_cli_tree_shows_prompt_ids_and_versions(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd())

    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "init", "demo-project"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    template = tmp_path / "prompt.yaml"
    _write_template(template)
    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "add", str(template)],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    _write_template(template, prompt="classify carefully", temperature=0.3)
    subprocess.run(
        [sys.executable, "-m", "pvm.cli", "add", str(template)],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pvm.cli", "tree"],
        cwd=tmp_path,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    output = result.stdout.strip()
    assert "demo-project" in output
    assert "intent_classifier" in output
    assert "0.1.0" in output
    assert "0.1.1" in output
