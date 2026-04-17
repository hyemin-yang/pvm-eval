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


def _first_matching_column(columns: list[str], candidates: list[str]) -> str:
    lowered = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return ""


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


def select_judge_component_file(run_dir: Path) -> Path | None:
    """Return the most appropriate judge component YAML for a run.

    Preference order:
    1. `judge_components/judge.yaml` - canonical editable file
    2. Latest non-timestamp `*_judge.yaml`
    3. Latest timestamped `*_judge_*.yaml`
    4. Any latest YAML file in `judge_components/`
    """
    comp_dir = run_dir / "judge_components"
    if not comp_dir.exists():
        return None

    canonical = comp_dir / "judge.yaml"
    if canonical.exists():
        return canonical

    direct_candidates = sorted(
        [p for p in comp_dir.glob("*_judge.yaml") if p.stem.endswith("_judge")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if direct_candidates:
        return direct_candidates[0]

    snapshot_candidates = sorted(
        comp_dir.glob("*_judge_*.yaml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if snapshot_candidates:
        return snapshot_candidates[0]

    any_yaml = sorted(comp_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
    if any_yaml:
        return any_yaml[0]

    return None


def get_csv_path(pvm_root: Path, csv_hash: str) -> Path:
    """등록된 CSV 파일 경로를 반환한다."""
    return pvm_root / "datasets" / csv_hash / "data.csv"


def get_prompt_path(pvm_root: Path, prompt_id: str, version: str) -> Path:
    """등록된 prompt.md 파일 경로를 반환한다."""
    return pvm_root / "prompts" / prompt_id / "versions" / version / "prompt.md"


# ── CSV 등록 ──────────────────────────────────────────────────────────────────

def register_csv(
    pvm_root: Path,
    csv_path: Path,
    original_path: Path | None = None,
) -> tuple[str, Path]:
    """CSV를 .pvm/datasets/{hash}/ 에 등록한다.

    이미 등록된 CSV는 복사하지 않고 기존 경로를 반환.

    Args:
        pvm_root: .pvm/ 디렉토리 경로
        csv_path: 등록할 CSV 파일 경로 (이미 csv 형태여야 함)
        original_path: 원본 파일 경로 (xlsx 등 변환 전 경로; 없으면 csv_path 사용)

    Returns:
        (csv_hash, registered_data_path)
    """
    import pandas as pd

    csv_hash = compute_csv_hash(csv_path)
    dataset_dir = datasets_dir(pvm_root) / csv_hash
    data_path = dataset_dir / "data.csv"

    if not data_path.exists():
        dataset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, data_path)

    # meta.json: SKILL.md 스키마 (original_path, row_count, columns 포함)
    df = pd.read_csv(data_path)
    meta = {
        "csv_hash": csv_hash,
        "original_path": str((original_path or csv_path).resolve()),
        "original_name": (original_path or csv_path).name,
        "dataset_name": (original_path or csv_path).stem,
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "row_count": len(df),
        "columns": list(df.columns),
        "trace_id_column": _first_matching_column(
            list(df.columns),
            ["trace_id", "scenario_id", "id", "sample_id", "row_id", "index"],
        ),
        "query_column": _first_matching_column(
            list(df.columns),
            ["user_input", "prompt", "input_prompt", "conversation", "dialogue", "history"],
        ),
        "response_column": _first_matching_column(
            list(df.columns),
            ["llm_output", "response", "output", "assistant_response"],
        ),
    }
    query_col = meta["query_column"]
    if query_col and query_col in df.columns:
        try:
            meta["query_count"] = int(df[query_col].fillna("").astype(str).str.strip().nunique())
        except Exception:
            meta["query_count"] = len(df)
    else:
        meta["query_count"] = len(df)
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
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
        "steps_completed": [],
    }
    _write_json(run_dir / "pipeline_meta.json", meta)

    return pipeline_hash, run_dir


def load_pipeline_meta(run_dir: Path) -> dict:
    """pipeline_meta.json을 로드한다."""
    meta_path = run_dir / "pipeline_meta.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def mark_step_completed(run_dir: Path, step: str) -> list[str]:
    """pipeline_meta.json의 steps_completed에 step을 추가한다.

    Returns:
        Updated steps_completed list
    """
    meta_path = run_dir / "pipeline_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    steps = list(dict.fromkeys(meta.get("steps_completed", [])))  # dedupe, preserve order
    if step not in steps:
        steps.append(step)
    meta["steps_completed"] = steps
    _write_json(meta_path, meta)
    return steps


def update_pipeline_status(run_dir: Path, status: str, **extra) -> None:
    """pipeline_meta.json의 status 필드를 갱신한다 (legacy 호환용)."""
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
    for run_dir in judge_dir.iterdir():
        meta_path = run_dir / "pipeline_meta.json"
        if meta_path.exists():
            runs.append(json.loads(meta_path.read_text(encoding="utf-8")))

    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
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
    """가장 최근 완료된 judge 결과를 반환한다 (step3 완료된 것 중 최신)."""
    runs = list_pipeline_runs(pvm_root, prompt_id, version)
    for run in runs:
        steps = run.get("steps_completed", [])
        # steps_completed 기반 (신) 또는 status=done (구) 모두 지원
        if "step3" in steps or run.get("status") == "done":
            return load_judge_results_from_pvm(
                pvm_root, prompt_id, version, run["pipeline_hash"]
            )
    return None


# ── Query Dataset 관리 ────────────────────────────────────────────────────────

def query_datasets_dir(pvm_root: Path, prompt_id: str) -> Path:
    """프롬프트별 query dataset 저장소 경로."""
    return pvm_root / "prompts" / prompt_id / "query_datasets"


def register_query_dataset(
    pvm_root: Path,
    prompt_id: str,
    csv_path: Path,
    name: str = "",
) -> tuple[str, Path]:
    """query dataset CSV를 등록하고 (dataset_id, data_path)를 반환한다."""
    import pandas as pd

    # 내용 기반 hash → 동일 파일 재업로드 시 중복 방지
    h = sha256()
    with open(csv_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    dataset_id = h.hexdigest()[:16]

    dest_dir = query_datasets_dir(pvm_root, prompt_id) / dataset_id
    data_path = dest_dir / "data.csv"

    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, data_path)

    df = pd.read_csv(data_path)
    columns = list(df.columns)
    meta = {
        "dataset_id": dataset_id,
        "name": name or csv_path.name,
        "original_name": csv_path.name,
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "row_count": len(df),
        "columns": columns,
        "trace_id_column": _first_matching_column(
            columns, ["trace_id", "scenario_id", "id", "sample_id", "row_id"]
        ),
        "query_column": _first_matching_column(
            columns, ["user_input", "prompt", "input_prompt", "conversation", "dialogue"]
        ),
    }
    _write_json(dest_dir / "meta.json", meta)
    return dataset_id, data_path


def list_query_datasets(pvm_root: Path, prompt_id: str) -> list[dict]:
    """프롬프트의 query dataset 목록을 최신 등록순으로 반환한다."""
    base = query_datasets_dir(pvm_root, prompt_id)
    if not base.exists():
        return []
    result = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            result.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    result.sort(key=lambda m: m.get("registered_at", ""), reverse=True)
    return result


def get_query_dataset(pvm_root: Path, prompt_id: str, dataset_id: str) -> tuple[Path, dict] | None:
    """(data_path, meta) 반환. 없으면 None."""
    d = query_datasets_dir(pvm_root, prompt_id) / dataset_id
    data_path = d / "data.csv"
    meta_path = d / "meta.json"
    if not data_path.exists() or not meta_path.exists():
        return None
    return data_path, json.loads(meta_path.read_text(encoding="utf-8"))


def delete_query_dataset(pvm_root: Path, prompt_id: str, dataset_id: str) -> bool:
    """query dataset 삭제. 성공 여부 반환."""
    d = query_datasets_dir(pvm_root, prompt_id) / dataset_id
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


def join_query_and_response(
    pvm_root: Path,
    prompt_id: str,
    dataset_id: str,
    response_csv_path: Path,
) -> tuple[Path, list[str]]:
    """query dataset + response CSV를 trace_id 기준으로 join해 완성 CSV를 반환한다.

    Returns:
        (joined_csv_path, missing_trace_ids)
        - joined_csv_path: 결합된 임시 CSV
        - missing_trace_ids: response에만 있고 query에 없는 trace_id 목록
    """
    import csv as _csv
    import tempfile

    result = get_query_dataset(pvm_root, prompt_id, dataset_id)
    if result is None:
        raise FileNotFoundError(f"Query dataset {dataset_id} not found")
    query_path, meta = result

    tid_col = meta.get("trace_id_column") or "trace_id"

    # query 로드 (trace_id → row)
    queries: dict[str, dict] = {}
    with open(query_path, encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            tid = (row.get(tid_col) or "").strip()
            if tid:
                queries[tid] = row

    # response 로드
    responses: list[dict] = []
    resp_fieldnames: list[str] = []
    with open(response_csv_path, encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        resp_fieldnames = list(reader.fieldnames or [])
        for row in reader:
            responses.append(row)

    # trace_id 컬럼 탐색 (response 측)
    resp_tid_col = _first_matching_column(
        resp_fieldnames, ["trace_id", "scenario_id", "id", "sample_id"]
    ) or tid_col

    missing: list[str] = []
    joined_rows: list[dict] = []
    query_cols = list(next(iter(queries.values()), {}).keys()) if queries else []
    all_cols_set: dict[str, None] = dict.fromkeys(query_cols)
    all_cols_set.update(dict.fromkeys(resp_fieldnames))
    all_fieldnames = list(all_cols_set)

    for resp_row in responses:
        tid = (resp_row.get(resp_tid_col) or "").strip()
        if tid in queries:
            merged = {**queries[tid], **resp_row}
        else:
            missing.append(tid)
            merged = dict(resp_row)
        joined_rows.append(merged)

    # 임시 파일에 저장
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w",
                                      encoding="utf-8", newline="")
    writer = _csv.DictWriter(tmp, fieldnames=all_fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(joined_rows)
    tmp.close()

    return Path(tmp.name), missing


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
