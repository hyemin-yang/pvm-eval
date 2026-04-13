from __future__ import annotations

from pathlib import Path

from ui import eval_runner


def test_bundled_pipeline_is_always_configured() -> None:
    assert eval_runner.is_configured() is True


def test_get_pipeline_dir_points_to_bundled_resources() -> None:
    pipeline_dir = eval_runner.get_pipeline_dir()

    assert pipeline_dir.name == "eval_pipeline"
    assert (pipeline_dir / "step0_generate_config.py").exists()
    assert (pipeline_dir / "step1_error_analysis.py").exists()
    assert (pipeline_dir / "step2_generate_judge_prompts.py").exists()
    assert (pipeline_dir / "step3_run_judge.py").exists()
    assert (pipeline_dir / "prompts" / "error_analysis_meta_prompt.md").exists()


def test_set_pipeline_dir_is_a_safe_noop_for_backwards_compatibility(tmp_path: Path) -> None:
    before = eval_runner.get_pipeline_dir()

    eval_runner.set_pipeline_dir(tmp_path / "external-pipeline")

    assert eval_runner.get_pipeline_dir() == before
