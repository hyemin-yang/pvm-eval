"""
Step 1: 에러 분석 (Error Analysis)

human-labeled CSV를 읽고 LLM을 이용해 실패 패턴을 카테고리화한다.

실행:
    python pipeline/step1_error_analysis.py --config config/baby_shark_shipwreck.yaml

출력:
    outputs/error_analysis.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

# 상위 디렉토리의 pipeline 모듈을 import하기 위한 경로 설정
sys.path.insert(0, str(Path(__file__).parent))
from llm_client import create_client

load_dotenv()

# error_analysis.json의 JSON 스키마 (LLM에 전달하는 참조용)
ERROR_ANALYSIS_JSON_SCHEMA = """{
  "task_name": "string — config의 task_name",
  "categories": [
    {
      "id": "string — snake_case 식별자 (예: scenario_contamination)",
      "name": "string — 한국어 카테고리명",
      "definition": "string — 이 카테고리가 어떤 실패인지 한 문장 정의",
      "example_trace_ids": ["number or string — 이 카테고리의 대표 Fail 트레이스 ID 2~3개"],
      "failure_rate": "number — 전체 트레이스 중 이 카테고리에서 Fail 비율 (0.0~1.0)",
      "action": "string — judge_prompt | code_check | ignore"
    }
  ],
  "trace_labels": {
    "<trace_id>": {
      "<category_id>": "Pass 또는 Fail"
    }
  }
}"""


def normalize_label(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"", "none", "null", "nan"}:
        return ""
    if text == "pass":
        return "Pass"
    if text == "fail":
        return "Fail"
    # pairwise winner 값 정규화
    if text == "a":
        return "A"
    if text == "b":
        return "B"
    if text == "same":
        return "SAME"
    return str(value).strip()


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(config: dict) -> pd.DataFrame:
    config_dir = Path(config.get("_config_dir", "."))
    csv_path = config_dir / config["input_csv"]
    return pd.read_csv(csv_path)


def build_conversation_text(row: pd.Series, cols: dict) -> str:
    conversation_col = cols.get("conversation", "")
    if conversation_col and conversation_col in row.index:
        return str(row[conversation_col]).strip()

    user_input_col = cols.get("user_input", "")
    llm_output_col = cols.get("llm_output", "")
    if user_input_col and llm_output_col and user_input_col in row.index and llm_output_col in row.index:
        user_input = str(row[user_input_col]).strip()
        llm_output = str(row[llm_output_col]).strip()
        parts = []
        if user_input:
            parts.append(user_input)
        if llm_output:
            parts.append(f"[AI] {llm_output}")
        return "\n".join(parts).strip()

    raise KeyError("columns에 conversation 또는 (user_input, llm_output)이 필요합니다.")


def build_pairwise_text(row: pd.Series, cols: dict) -> str:
    """pairwise 트레이스용: 프롬프트 + Response A + Response B를 포매팅한다."""
    parts: list[str] = []

    conversation_col = cols.get("conversation", "")
    user_input_col = cols.get("user_input", "")
    if conversation_col and conversation_col in row.index:
        parts.append(f"Prompt:\n{str(row[conversation_col]).strip()}")
    elif user_input_col and user_input_col in row.index:
        parts.append(f"Prompt:\n{str(row[user_input_col]).strip()}")

    response_a_col = cols.get("response_a", "")
    response_b_col = cols.get("response_b", "") or cols.get("llm_output", "")
    if response_a_col and response_a_col in row.index:
        parts.append(f"Response A:\n{str(row[response_a_col]).strip()}")
    if response_b_col and response_b_col in row.index:
        parts.append(f"Response B:\n{str(row[response_b_col]).strip()}")

    return "\n\n".join(parts).strip()


def format_traces_for_analysis(df: pd.DataFrame, cols: dict, judge_type: str = "pointwise") -> str:
    """모든 트레이스를 LLM에 전달할 텍스트로 포매팅한다.

    pointwise: Fail 트레이스와 llm_label ≠ human_label 불일치 케이스를 우선 포함.
    pairwise:  winner가 A 또는 B인 트레이스(우열이 있는 케이스)를 중심으로 포매팅.
    """
    lines = []
    trace_id_col = cols["trace_id"]
    human_reason_col = cols.get("human_reason", "")

    if judge_type == "pairwise":
        winner_col = cols.get("winner", "")
        if not winner_col:
            raise KeyError("pairwise judge_type에는 columns.winner가 필요합니다.")

        for _, row in df.iterrows():
            trace_id = row[trace_id_col]
            winner = normalize_label(row[winner_col])
            human_reason = row.get(human_reason_col, "") if human_reason_col else ""

            tag_map = {"A": "[A 우세]", "B": "[B 우세]", "SAME": "[동점]"}
            tag = tag_map.get(winner, f"[{winner}]")

            content = build_pairwise_text(row, cols)
            entry = (
                f"--- 트레이스 ID: {trace_id} {tag} ---\n"
                f"{content}\n"
            )
            if human_reason and pd.notna(human_reason) and str(human_reason).strip():
                entry += f"human_reason: {human_reason}\n"
            lines.append(entry)

    else:
        human_label_col = cols["human_label"]
        llm_label_col_candidate = cols.get("llm_label", "")
        llm_label_col = (
            llm_label_col_candidate
            if llm_label_col_candidate and llm_label_col_candidate in df.columns
            else ""
        )

        for _, row in df.iterrows():
            trace_id = row[trace_id_col]
            human_label = normalize_label(row[human_label_col])
            human_reason = row.get(human_reason_col, "") if human_reason_col else ""
            llm_label = normalize_label(row[llm_label_col]) if llm_label_col else None

            is_disagreement = (
                llm_label is not None
                and pd.notna(llm_label)
                and pd.notna(human_label)
                and str(llm_label).strip() != str(human_label).strip()
            )

            if human_label == "Fail":
                tag = "[FAIL]"
            elif is_disagreement:
                tag = "[불일치: LLM={llm_label}]".format(llm_label=llm_label)
            else:
                tag = "[PASS]"

            conversation = build_conversation_text(row, cols)
            entry = (
                f"--- 트레이스 ID: {trace_id} {tag} ---\n"
                f"대화:\n{conversation}\n"
            )
            if human_reason and pd.notna(human_reason) and str(human_reason).strip():
                entry += f"human_reason: {human_reason}\n"
            lines.append(entry)

    return "\n".join(lines)


def get_category_count_guidance(fail_count: int) -> str:
    """Fail 트레이스 개수에 따라 적절한 카테고리 수 권고 범위를 반환한다."""
    if fail_count < 5:
        return "2~3개"
    elif fail_count < 15:
        return "3~5개"
    elif fail_count < 30:
        return "4~7개"
    elif fail_count < 60:
        return "5~8개"
    else:
        return "5~10개"


def build_system_prompt(
    meta_prompt_text: str,
    system_prompt_text: str,
    fail_traces: str,
    fail_count: int,
) -> str:
    """메타 프롬프트의 플레이스홀더를 실제 값으로 대체한다."""
    return meta_prompt_text.replace(
        "{task_description}", system_prompt_text
    ).replace(
        "{fail_traces}", fail_traces
    ).replace(
        "{json_schema}", ERROR_ANALYSIS_JSON_SCHEMA
    ).replace(
        "{category_count_guidance}", get_category_count_guidance(fail_count)
    )


def compute_failure_rates(categories: list, trace_labels: dict, total: int) -> list:
    """trace_labels를 기반으로 각 카테고리의 failure_rate를 계산한다."""
    counts = {cat["id"]: 0 for cat in categories}
    for labels in trace_labels.values():
        for cat_id, label in labels.items():
            if label == "Fail" and cat_id in counts:
                counts[cat_id] += 1

    for cat in categories:
        count = counts.get(cat["id"], 0)
        cat["fail_count"] = count
        cat["failure_rate"] = round(count / total, 4) if total > 0 else 0.0
    return categories


def run(config_path: str) -> None:
    config = load_config(config_path)
    config_path_obj = Path(config_path).resolve()
    config["_config_dir"] = str(config_path_obj.parent)

    cols = config["columns"]
    judge_type = config.get("judge_type", "pointwise")
    system_prompt_text = config.get("system_prompt") or config.get("task_description", "")
    task_name = config["task_name"]
    output_dir = Path(config.get("output_dir", "./outputs"))
    if not output_dir.is_absolute():
        output_dir = config_path_obj.parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 메타 프롬프트 로드 (step1 스크립트 기준 상대 경로)
    prompts_dir = Path(__file__).parent / "prompts"
    meta_prompt_path = prompts_dir / "error_analysis_meta_prompt.md"
    with open(meta_prompt_path, encoding="utf-8") as f:
        meta_prompt_text = f.read()

    # CSV 로드
    df = load_csv(config)
    raw_total_traces = len(df)
    print(f"[Step 1] 트레이스 {raw_total_traces}개 로드 완료 (judge_type: {judge_type})")

    # 라벨 컬럼 결정 (pointwise: human_label, pairwise: winner)
    if judge_type == "pairwise":
        label_col = cols.get("winner", "")
        if not label_col:
            raise KeyError("pairwise judge_type에는 columns.winner가 필요합니다.")
    else:
        label_col = cols["human_label"]

    normalized_labels = df[label_col].map(normalize_label)
    excluded_count = int(normalized_labels.eq("").sum())
    if excluded_count:
        df = df.loc[~normalized_labels.eq("")].copy()
        print(f"[Step 1] {label_col} 비어있는 행 {excluded_count}개 제외")

    total_traces = len(df)
    if total_traces == 0:
        raise ValueError(f"분석 가능한 트레이스가 없습니다. {label_col} 값을 확인하세요.")

    # 트레이스 포매팅
    traces_text = format_traces_for_analysis(df, cols, judge_type=judge_type)

    # 핵심 케이스 개수 계산 (카테고리 수 권고 범위 결정용)
    # pointwise: Fail 개수 / pairwise: A 또는 B (우열이 있는) 개수
    if judge_type == "pairwise":
        fail_count = int(normalized_labels.isin(["A", "B"]).sum())
        print(f"[Step 1] A/B 우열 트레이스: {fail_count}개 / 동점: {int(normalized_labels.eq('SAME').sum())}개 / 전체: {total_traces}개")
    else:
        fail_count = int(normalized_labels.eq("Fail").sum())
        print(f"[Step 1] Fail 트레이스: {fail_count}개 / 전체: {total_traces}개")
    print(f"[Step 1] 카테고리 권고 범위: {get_category_count_guidance(fail_count)}")

    # 시스템 프롬프트 구성
    system_prompt = build_system_prompt(meta_prompt_text, system_prompt_text, traces_text, fail_count)

    user_message = (
        "위 트레이스들을 분석하여 실패 카테고리를 도출하고, "
        "모든 트레이스에 카테고리별 이진 라벨을 부여해주세요. "
        "반드시 JSON만 출력하세요."
    )

    # LLM 호출
    client = create_client(config["llm"])
    print(f"[Step 1] LLM 호출 중 ({config['llm']['provider']} / {config['llm']['model']})...")
    result = client.call_json(system_prompt, user_message)

    # task_name 보정
    result["task_name"] = task_name

    # failure_rate 보정 계산 (LLM이 계산한 값을 실제 trace_labels로 검증/덮어쓰기)
    if "categories" in result and "trace_labels" in result:
        result["categories"] = compute_failure_rates(
            result["categories"], result["trace_labels"], total_traces
        )

    # 저장
    output_path = output_dir / "error_analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    snapshot_path = output_dir / f"error_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 결과 요약 출력
    categories = result.get("categories", [])
    print(f"\n[Step 1] 완료 → {output_path}")
    print(f"  스냅샷 저장 → {snapshot_path}")
    print(f"  발견된 실패 카테고리: {len(categories)}개")
    print()
    for cat in categories:
        action_icon = {"judge_prompt": "⚖️ ", "code_check": "🔧", "ignore": "💤"}.get(
            cat["action"], "  "
        )
        print(
            f"  {action_icon} [{cat['action']:12s}] {cat['name']} "
            f"(실패율 {cat['failure_rate']*100:.1f}%) — {cat['definition']}"
        )

    labeled_count = len(result.get("trace_labels", {}))
    print(f"\n  라벨링된 트레이스: {labeled_count}/{total_traces}개")

    judge_prompt_count = sum(1 for c in categories if c.get("action") == "judge_prompt")
    print(f"  judge component 생성 필요: {judge_prompt_count}개 카테고리")
    print("\n다음 단계: python pipeline/step2_generate_judge_prompts.py --config <config>")


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 1: 에러 분석")
    parser.add_argument(
        "--config",
        required=True,
        help="config YAML 파일 경로 (예: config/baby_shark_shipwreck.yaml)",
    )
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
