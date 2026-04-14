"""
PVM 통합 Eval 파이프라인 실행 서비스

eval-ui의 pipeline_runner.py에 대응하는 PVM 내장 버전.
모든 출력은 .pvm/prompts/{id}/versions/{ver}/judge/{pipeline_hash}/ 에 저장.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import IO

import yaml

from pvm.eval_pipeline.pvm_storage import select_judge_component_file

# ── 전역 상태 ────────────────────────────────────────────────────────────────

_running_jobs: dict[str, tuple[subprocess.Popen, IO]] = {}
_log_dir: Path = Path(tempfile.gettempdir()) / "pvm_eval_logs"
_log_dir.mkdir(parents=True, exist_ok=True)

SCRIPTS = {
    0: "step0_generate_config.py",
    1: "step1_error_analysis.py",
    2: "step2_generate_judge_prompts.py",
    3: "step3_run_judge.py",
}


# ── 초기화 ───────────────────────────────────────────────────────────────────

def get_pipeline_dir() -> Path:
    """번들된 eval_pipeline 패키지 디렉토리를 반환."""
    import pvm.eval_pipeline as _ep
    return Path(_ep.__file__).parent


def is_configured() -> bool:
    return True


def set_pipeline_dir(pipeline_dir: Path) -> None:
    """하위 호환성을 위해 유지. 번들된 파이프라인을 사용하므로 무시됩니다."""
    pass


# ── 경로/키 헬퍼 ─────────────────────────────────────────────────────────────

def _job_key(prompt_id: str, version: str, pipeline_hash: str, step: int) -> str:
    return f"{prompt_id}__{version}__{pipeline_hash}__step{step}"


def _log_path(prompt_id: str, version: str, pipeline_hash: str, step: int) -> Path:
    return _log_dir / f"{_job_key(prompt_id, version, pipeline_hash, step)}.log"


def _python_executable() -> str:
    return sys.executable


def _make_env() -> dict:
    pipeline_dir = get_pipeline_dir()
    return {**os.environ, "PYTHONPATH": str(pipeline_dir)}


# ── Step 0 (동기) ─────────────────────────────────────────────────────────────

def run_step0_sync(
    run_dir: Path,
    csv_path: Path,
    system_prompt: str,
    provider: str,
    model: str,
    judge_type: str,
    prompt_id: str = "prompt",
) -> dict:
    """config.yaml 생성. 동기 실행 (빠름)."""
    pipeline_dir = get_pipeline_dir()

    # prompt_id를 파일명으로 써야 step0에서 task_name이 prompt_id로 설정됨
    prompt_file = run_dir / f"{prompt_id}.md"
    prompt_file.write_text(system_prompt, encoding="utf-8")

    cmd = [
        _python_executable(),
        str(pipeline_dir / SCRIPTS[0]),
        "--csv", str(csv_path),
        "--prompt", str(prompt_file),
        "--provider", provider,
        "--model", model,
        "--judge-type", judge_type,
        "--output", str(run_dir / "config.yaml"),
    ]
    result = subprocess.run(
        cmd, cwd=str(pipeline_dir),
        capture_output=True, text=True, timeout=120,
        env=_make_env(),
    )
    combined = (result.stdout + "\n" + result.stderr).strip()
    return {"success": result.returncode == 0, "output": combined}


# ── Step 1~3 (비동기) ─────────────────────────────────────────────────────────

def start_step_async(
    prompt_id: str, version: str, pipeline_hash: str,
    step: int, run_dir: Path,
) -> None:
    pipeline_dir = get_pipeline_dir()
    key = _job_key(prompt_id, version, pipeline_hash, step)

    if key in _running_jobs:
        proc, f = _running_jobs[key]
        if proc.poll() is not None:
            try: f.close()
            except Exception: pass
            del _running_jobs[key]

    lpath = _log_path(prompt_id, version, pipeline_hash, step)
    lpath.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        _python_executable(), str(pipeline_dir / SCRIPTS[step]),
        "--config", str(run_dir / "config.yaml"),
    ]
    f = open(lpath, "w", buffering=1, encoding="utf-8")
    proc = subprocess.Popen(
        cmd, cwd=str(pipeline_dir),
        stdout=f, stderr=subprocess.STDOUT, text=True,
        env=_make_env(),
    )
    _running_jobs[key] = (proc, f)


def get_step_status(
    prompt_id: str, version: str, pipeline_hash: str, step: int
) -> str:
    """'running' | 'done' | 'failed' | 'idle'"""
    key = _job_key(prompt_id, version, pipeline_hash, step)
    if key not in _running_jobs:
        return "idle"
    proc, f = _running_jobs[key]
    retcode = proc.poll()
    if retcode is None:
        return "running"
    try: f.close()
    except Exception: pass
    del _running_jobs[key]
    return "done" if retcode == 0 else "failed"


def stop_step(
    prompt_id: str, version: str, pipeline_hash: str, step: int
) -> None:
    key = _job_key(prompt_id, version, pipeline_hash, step)
    if key not in _running_jobs:
        return
    proc, f = _running_jobs[key]
    proc.terminate()
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired: proc.kill()
    try: f.close()
    except Exception: pass
    del _running_jobs[key]


def is_running(prompt_id: str, version: str, pipeline_hash: str, step: int) -> bool:
    return get_step_status(prompt_id, version, pipeline_hash, step) == "running"


def load_log(
    prompt_id: str, version: str, pipeline_hash: str, step: int
) -> str | None:
    p = _log_path(prompt_id, version, pipeline_hash, step)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


# ── 결과 로드 ─────────────────────────────────────────────────────────────────

def load_json(run_dir: Path, filename: str) -> dict | None:
    p = run_dir / filename
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_step2_yaml(run_dir: Path) -> dict | None:
    comp_file = select_judge_component_file(run_dir)
    if comp_file is None:
        return None
    with open(comp_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_run_status(run_dir: Path) -> dict:
    """어느 단계까지 완료됐는지 반환."""
    step1 = (run_dir / "error_analysis.json").exists()
    step2 = select_judge_component_file(run_dir) is not None
    step3 = (run_dir / "judge_results.json").exists()
    return {"step1": step1, "step2": step2, "step3": step3}


# ── config 패치 ───────────────────────────────────────────────────────────────

def patch_config_for_pvm(run_dir: Path, pvm_ref: dict) -> None:
    """Step0 생성 config.yaml에 pvm_ref와 output_dir 추가."""
    cfg_path = run_dir / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["pvm_ref"] = pvm_ref
    cfg["output_dir"] = str(run_dir)
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
