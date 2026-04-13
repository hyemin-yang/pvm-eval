"""
PVM 통합 저장소 유틸리티

.pvm/ 디렉토리 구조에 eval 결과를 읽고 쓰는 함수들.

디렉토리 구조:
  .pvm/
    datasets/{csv_hash}/
      data.csv
      meta.json
    prompts/{prompt_id}/versions/{version}/judge/{pipeline_hash}/
      pipeline_meta.json
      config.yaml
      error_analysis.json
      judge_components/judge.yaml
      judge_results.json
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


# ── 해시 계산 ────────────────────────────────────────────────────────────────

def compute_csv_hash(csv_path: Path) -> str:
    """CSV 파일 내용 기반 sha256 앞 16자."""
    h = sha256()
    with open(csv_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


def compute_pipeline_hash(
    csv_hash: str,
    prompt_id: str,
    prompt_version: str,
    judge_type: str,
    created_at: str,
) -> str:
    """파이프라인 실행 1회 고유 해시 (sha256 앞 12자).

    hash_input = f"{csv_hash}:{prompt_id}:{prompt_version}:{judge_type}:{created_at}"
    """
    hash_input = f"{csv_hash}:{prompt_id}:{prompt_version}:{judge_type}:{created_at}"
    return sha256(hash_input.encode()).hexdigest()[:12]


# ── 경로 헬퍼 ─────────────────────────────────────────────────────────────────

def datasets_dir(pvm_root: Path) -> Path:
    return pvm_root / "datasets"


def judge_run_dir(pvm_root: Path, prompt_id: str, version: str, pipeline_hash: str) -> Path:
    return pvm_root / "prompts" / prompt_id / "versions" / version / "judge" / pipeline_hash


# ── CSV 등록 ──────────────────────────────────────────────────────────────────

def register_csv(pvm_root: Path, csv_path: Path) -> tuple[str, Path]:
    """CSV를 .pvm/datasets/{hash}/ 에 등록한다.

    이미 등록된 CSV는 복사하지 않고 기존 경로를 반환.

    Returns:
        (csv_hash, registered_data_path)
    """
    csv_hash = compute_csv_hash(csv_path)
    dataset_dir = datasets_dir(pvm_root) / csv_hash
    data_path = dataset_dir / "data.csv"

    if not data_path.exists():
        dataset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, data_path)
        meta = {
            "csv_hash": csv_hash,
            "original_name": csv_path.name,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": csv_path.stat().st_size,
        }
        (dataset_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return csv_hash, data_path


# ── 파이프라인 실행 생성 ──────────────────────────────────────────────────────

def create_pipeline_run(
    pvm_root: Path,
    prompt_id: str,
    prompt_version: str,
    judge_type: str,
    csv_hash: str,
    judge_model: str,
    judge_provider: str,
) -> tuple[str, Path]:
    """파이프라인 실행 디렉토리를 생성하고 pipeline_meta.json을 기록한다.

    Returns:
        (pipeline_hash, run_dir)
    """
    created_at = datetime.now(timezone.utc).isoformat()
    pipeline_hash = compute_pipeline_hash(
        csv_hash=csv_hash,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        judge_type=judge_type,
        created_at=created_at,
    )

    run_dir = judge_run_dir(pvm_root, prompt_id, prompt_version, pipeline_hash)
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "pipeline_hash": pipeline_hash,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "judge_type": judge_type,
        "csv_hash": csv_hash,
        "judge_model": judge_model,
        "judge_provider": judge_provider,
        "created_at": created_at,
        "status": "initialized",  # initialized → running → done | failed
    }
    _write_json(run_dir / "pipeline_meta.json", meta)

    return pipeline_hash, run_dir


def update_pipeline_status(run_dir: Path, status: str, **extra) -> None:
    """pipeline_meta.json의 status 필드를 갱신한다."""
    meta_path = run_dir / "pipeline_meta.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = status
    meta.update(extra)
    _write_json(meta_path, meta)


# ── 실행 이력 조회 ────────────────────────────────────────────────────────────

def list_pipeline_runs(pvm_root: Path, prompt_id: str, version: str) -> list[dict]:
    """특정 버전의 judge 실행 이력을 최신순으로 반환한다."""
    judge_dir = pvm_root / "prompts" / prompt_id / "versions" / version / "judge"
    if not judge_dir.exists():
        return []

    runs = []
    for run_dir in sorted(judge_dir.iterdir(), reverse=True):
        meta_path = run_dir / "pipeline_meta.json"
        if meta_path.exists():
            runs.append(json.loads(meta_path.read_text(encoding="utf-8")))
    return runs


def load_judge_results_from_pvm(
    pvm_root: Path, prompt_id: str, version: str, pipeline_hash: str
) -> dict | None:
    """특정 pipeline 실행의 judge_results.json을 로드한다."""
    p = judge_run_dir(pvm_root, prompt_id, version, pipeline_hash) / "judge_results.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def latest_judge_result(pvm_root: Path, prompt_id: str, version: str) -> dict | None:
    """가장 최근 완료된 judge 결과를 반환한다 (status=done인 것 중 최신)."""
    runs = list_pipeline_runs(pvm_root, prompt_id, version)
    for run in runs:
        if run.get("status") == "done":
            return load_judge_results_from_pvm(
                pvm_root, prompt_id, version, run["pipeline_hash"]
            )
    return None


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
