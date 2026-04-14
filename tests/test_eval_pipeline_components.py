from __future__ import annotations

from pathlib import Path

import yaml

from pvm.eval_pipeline.pvm_storage import select_judge_component_file
from ui.eval_runner import load_step2_yaml


def _write_yaml(path: Path, criteria: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"criteria": criteria}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_load_step2_yaml_prefers_canonical_judge_yaml(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    comp_dir = run_dir / "judge_components"
    _write_yaml(comp_dir / "task_judge.yaml", "old criteria")
    _write_yaml(comp_dir / "judge.yaml", "edited criteria")

    result = load_step2_yaml(run_dir)

    assert result is not None
    assert result["criteria"] == "edited criteria"


def test_select_judge_component_file_falls_back_to_timestamped_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    comp_dir = run_dir / "judge_components"
    _write_yaml(comp_dir / "task_judge_20260414_120000.yaml", "snapshot criteria")

    selected = select_judge_component_file(run_dir)

    assert selected == comp_dir / "task_judge_20260414_120000.yaml"
