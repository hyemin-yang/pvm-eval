"""
Step 3: Judge 직접 실행

Step 2에서 생성한 judge 컴포넌트와 데이터 스플릿을 이용해
LLM judge를 직접 실행하고 결과를 JSON으로 저장합니다.

Usage:
    python pipeline/step3_run_judge.py --config config/<task>/config.yaml
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import signal

import yaml
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from judge_composer import JudgePromptComposer, load_components
from llm_client import create_client


# ─────────────────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict:
    """마크다운 코드 펜스 제거 후 JSON 파싱."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return json.loads(text)


def parse_judge_output(raw: str, judge_type: str) -> dict:
    """Judge LLM 응답을 파싱해 verdict + 상세 정보를 반환."""
    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        return {"verdict": "PARSE_ERROR", "error": str(e), "raw": raw}

    if judge_type == "pairwise":
        choice = str(data.get("pairwise_choice", "")).strip().upper()
        if choice not in ("A", "B", "SAME"):
            return {
                "verdict": "PARSE_ERROR",
                "error": f"Invalid pairwise_choice: {choice!r}",
                "raw": raw,
            }
        return {"verdict": choice, "explanation": data.get("explanation", "")}
    else:  # pointwise
        criteria_results = data.get("criteria_results", [])
        if not criteria_results:
            return {"verdict": "PARSE_ERROR", "error": "criteria_results 없음", "raw": raw}
        all_pass = all(
            str(r.get("result", "")).strip().lower() == "pass" for r in criteria_results
        )
        return {
            "verdict": "Pass" if all_pass else "Fail",
            "criteria_results": criteria_results,
        }


def compute_metrics(results: list[dict], judge_type: str) -> dict:
    """평가 결과로부터 메트릭을 계산한다."""
    # excluded_from_metrics=True인 행(human_label 없음)은 제외
    metric_results = [r for r in results if not r.get("excluded_from_metrics")]
    total = len(metric_results)
    error_count = sum(1 for r in metric_results if r["judge_verdict"] == "PARSE_ERROR")
    valid = [r for r in metric_results if r["judge_verdict"] != "PARSE_ERROR"]

    if judge_type == "pairwise":
        correct = sum(1 for r in valid if r["judge_verdict"] == r["human_label"])
        return {
            "total": total,
            "valid": len(valid),
            "error_count": error_count,
            "accuracy": round(correct / len(valid), 4) if valid else 0.0,
            "correct": correct,
        }

    # pointwise
    tp = sum(1 for r in valid if r["judge_verdict"] == "Pass" and r["human_label"] == "Pass")
    tn = sum(1 for r in valid if r["judge_verdict"] == "Fail" and r["human_label"] == "Fail")
    fp = sum(1 for r in valid if r["judge_verdict"] == "Pass" and r["human_label"] == "Fail")
    fn = sum(1 for r in valid if r["judge_verdict"] == "Fail" and r["human_label"] == "Pass")
    accuracy = (tp + tn) / len(valid) if valid else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "total": total,
        "valid": len(valid),
        "error_count": error_count,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="config.yaml 경로")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    with open(cfg_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    task_name = config["task_name"]
    judge_type = config.get("judge_type", "pointwise")
    _raw_output_dir = config.get("output_dir", "./outputs")
    output_dir = Path(_raw_output_dir) if Path(_raw_output_dir).is_absolute() else cfg_path.parent / _raw_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Step3] Task: {task_name}  judge_type: {judge_type}", flush=True)

    # ── 컴포넌트 로드 ─────────────────────────────────────────────────────
    comp_dir = output_dir / "judge_components"
    comp_candidates = sorted(
        [p for p in comp_dir.glob("*_judge.yaml") if p.stem.endswith("_judge")],
        key=lambda p: p.stat().st_mtime, reverse=True,
    ) if comp_dir.exists() else []
    if not comp_candidates:
        comp_candidates = sorted(comp_dir.glob("*_judge.yaml"), key=lambda p: p.stat().st_mtime, reverse=True) if comp_dir.exists() else []
    if not comp_candidates:
        print(f"❌ Judge 컴포넌트 없음: {comp_dir}", flush=True)
        sys.exit(1)
    comp_path = comp_candidates[0]
    print(f"[Step3] 컴포넌트 파일: {comp_path.name}", flush=True)
    components = load_components(comp_path)
    print(f"[Step3] 컴포넌트 로드 (few-shot: {len(components.few_shot)}개)", flush=True)

    # ── CSV 로드 (전체 데이터가 평가 대상) ───────────────────────────────────
    cols = config.get("columns", {})
    col_tid = cols.get("trace_id", "trace_id")
    col_ui = cols.get("user_input", "user_input")
    col_lo = cols.get("llm_output", "llm_output")
    col_hl = cols.get("human_label", "pass_fail")
    col_hr = cols.get("human_reason", "critique")
    col_conv = cols.get("conversation", "conversation")
    col_ra = cols.get("response_a", "response_a")
    col_hw = cols.get("human_winner", "winner")

    csv_path_raw = config.get("input_csv", "")
    csv_path = Path(csv_path_raw)
    if not csv_path.is_absolute():
        csv_path = cfg_path.parent / csv_path

    def _norm_label(v: str) -> str:
        """pass/fail/Pass/Fail/PASS/FAIL → Pass/Fail, 그 외 원본 유지."""
        s = v.strip().lower()
        if s == "pass":
            return "Pass"
        if s == "fail":
            return "Fail"
        return v.strip()

    trace_data: dict[str, dict] = {}
    eval_ids: list[str] = []  # CSV 원본 순서 유지
    with open(csv_path, encoding="utf-8-sig") as f:  # utf-8-sig: BOM 자동 제거
        for row in csv.DictReader(f):
            tid = row.get(col_tid, "").strip()
            if tid:
                trace_data[tid] = {
                    "user_input": row.get(col_ui, ""),
                    "llm_output": row.get(col_lo, ""),
                    "human_label": _norm_label(row.get(col_hl, "")),
                    "human_reason": row.get(col_hr, ""),
                    "conversation": row.get(col_conv, ""),
                    "response_a": row.get(col_ra, ""),
                    "human_winner": row.get(col_hw, ""),
                }
                eval_ids.append(tid)

    print(f"[Step3] 평가 대상: CSV 전체 {len(eval_ids)}개 trace", flush=True)

    # ── LLM 클라이언트 ────────────────────────────────────────────────────
    llm = create_client(config["llm"])
    composer = JudgePromptComposer()
    reference = config.get("system_prompt", "")
    print(
        f"[Step3] LLM: {config['llm'].get('provider')} / {config['llm'].get('model')}",
        flush=True,
    )
    print("=" * 60, flush=True)

    # ── SIGTERM 핸들러: 중지 시 부분 결과 저장 ───────────────────────────
    _stop_requested = False

    def _handle_sigterm(signum, frame):
        nonlocal _stop_requested
        _stop_requested = True
        print("\n[Step3] 중지 요청 받음. 현재 trace 완료 후 저장합니다...", flush=True)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    results_path = output_dir / "judge_results.json"

    def _save_results(results: list[dict], is_partial: bool = False) -> None:
        metrics = compute_metrics(results, judge_type)
        output = {
            "task_name": task_name,
            "judge_type": judge_type,
            "model": config["llm"].get("model", ""),
            "provider": config["llm"].get("provider", ""),
            "run_at": datetime.now(timezone.utc).isoformat(),
            "partial": is_partial,
            "metrics": metrics,
            "results": results,
        }
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 평가 실행 ─────────────────────────────────────────────────────────
    results: list[dict] = []
    for i, trace_id in enumerate(eval_ids):
        if _stop_requested:
            print(f"[Step3] 중지: {i}개 완료, 결과 저장 후 종료", flush=True)
            break
        trace = trace_data.get(trace_id)
        if trace is None:
            print(f"[{i+1}/{len(eval_ids)}] ⚠️  '{trace_id}' CSV에 없음, skip", flush=True)
            continue

        print(f"[{i+1}/{len(eval_ids)}] {trace_id}", end=" ", flush=True)

        try:
            if judge_type == "pairwise":
                system_msg, user_msg = composer.compose(
                    components,
                    reference=reference,
                    prompt=trace["user_input"],
                    response=trace["llm_output"],
                    baseline_model_response=trace["response_a"],
                )
                human_label = trace["human_winner"]
            else:
                system_msg, user_msg = composer.compose(
                    components,
                    reference=reference,
                    prompt=trace["user_input"],
                    response=trace["llm_output"],
                )
                human_label = trace["human_label"]

            raw = llm.call(system_msg, user_msg)
            parsed = parse_judge_output(raw, judge_type)
        except Exception as e:
            parsed = {"verdict": "PARSE_ERROR", "error": str(e)}
            human_label = (
                trace["human_winner"] if judge_type == "pairwise" else trace["human_label"]
            )

        verdict = parsed["verdict"]

        # human_label이 비어있으면 혼동행렬에서 제외 (테이블엔 표시)
        if not human_label.strip():
            print(f"→ {verdict} (라벨 없음)", flush=True)
            results.append({
                "trace_id": trace_id,
                "split": "eval",
                "human_label": "",
                "human_reason": trace["human_reason"],
                "judge_verdict": verdict,
                "judge_detail": parsed,
                "excluded_from_metrics": True,
            })
            _save_results(results, is_partial=True)
            continue

        if verdict == "PARSE_ERROR":
            marker = "⚠️"
        elif verdict == human_label:
            marker = "✅"
        else:
            marker = "❌"
        print(f"→ {verdict} {marker}", flush=True)

        results.append({
            "trace_id": trace_id,
            "split": "eval",
            "human_label": human_label,
            "human_reason": trace["human_reason"],
            "judge_verdict": verdict,
            "judge_detail": parsed,
        })
        # 매 trace마다 증분 저장 → SIGKILL 와도 직전까지 보존
        _save_results(results, is_partial=True)

    print("=" * 60, flush=True)

    # ── 최종 저장 (partial=False로 덮어씀) ───────────────────────────────
    _save_results(results, is_partial=_stop_requested)
    metrics = compute_metrics(results, judge_type)

    print(f"[Step3] 정확도: {metrics['accuracy']:.1%}  ({metrics.get('valid',0)}/{metrics.get('total',0)}건)", flush=True)
    if judge_type == "pointwise" and "confusion" in metrics:
        c = metrics["confusion"]
        print(f"[Step3] TP={c['tp']} TN={c['tn']} FP={c['fp']} FN={c['fn']}", flush=True)
        print(f"[Step3] Precision={metrics['precision']:.3f}  Recall={metrics['recall']:.3f}  F1={metrics['f1']:.3f}", flush=True)
    if metrics["error_count"] > 0:
        print(f"[Step3] ⚠️  파싱 에러 {metrics['error_count']}건", flush=True)

    if _stop_requested:
        print(f"⏹ 중지됨. 부분 결과 저장 완료 ({len(results)}건): {results_path}", flush=True)
    else:
        print(f"✅ 완료! 결과: {results_path}", flush=True)


if __name__ == "__main__":
    main()
