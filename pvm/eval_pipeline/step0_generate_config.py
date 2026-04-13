"""
Step 0: Config 자동 생성

review-interface에서 export한 CSV와 검수 대상 system prompt를 읽어
pipeline config YAML을 자동 생성한다.

실행:
    python pipeline/step0_generate_config.py --csv data/labeled.csv --prompt prompts/system.md

출력:
    config/{task_name}.yaml  (또는 --output 경로)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

# review-interface export 컬럼명을 우선 지원
COLUMN_PATTERNS: dict[str, list[str]] = {
    "trace_id": ["trace_id", "scenario_id", "id", "idx", "index", "row_id", "sample_id"],
    "conversation": ["conversation", "history", "dialog", "dialogue", "text", "content", "messages", "chat", "input"],
    "user_input": ["user_input", "prompt", "input_prompt", "request"],
    "llm_output": ["llm_output", "response", "output", "assistant_response", "model_output"],
    "human_label": ["pass_fail", "human_label", "label", "ground_truth", "gt", "answer", "human_eval", "correct"],
    "human_reason": ["critique", "human_reason", "reason", "note", "comment", "feedback", "explanation", "why"],
    "category": ["category", "failure_category", "label_category"],
    "llm_label": ["llm_label", "model_label", "pred", "prediction", "auto_label", "ai_label", "llm_eval"],
    "few_shot_type": ["few_shot_type", "fewshot_type", "shot_type", "example_type"],
    # pairwise 전용 컬럼
    "response_a": ["response_a", "baseline_response", "model_a_response", "response_a_text"],
    "response_b": ["response_b", "model_b_response", "response_b_text"],
    "winner": ["winner", "pairwise_label", "pairwise_result", "pairwise_choice", "choice"],
}

GENERIC_FILENAMES = {
    "system_prompt", "prompt", "system", "config", "main",
    "assistant", "agent", "chatbot", "llm",
}


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    """DataFrame 컬럼명을 휴리스틱으로 분석해 config columns 매핑을 추론한다."""
    csv_cols_lower = {col.lower(): col for col in df.columns}
    mapping: dict[str, str] = {}

    for field, patterns in COLUMN_PATTERNS.items():
        for pattern in patterns:
            if pattern in csv_cols_lower:
                mapping[field] = csv_cols_lower[pattern]
                break

    return mapping


def detect_columns_verbose(
    df: pd.DataFrame,
    judge_type: str = "pointwise",
) -> tuple[dict[str, str], list[str]]:
    """컬럼 감지 결과와 매핑되지 않은 필수 필드 목록을 함께 반환한다."""
    mapping = detect_columns(df)
    missing: list[str] = []
    if "trace_id" not in mapping:
        missing.append("trace_id")

    if judge_type == "pairwise":
        # pairwise: winner 컬럼 필수, response_a + (response_b 또는 llm_output) 필요
        if "winner" not in mapping:
            missing.append("winner")
        has_response_b = "response_b" in mapping or "llm_output" in mapping
        if "response_a" not in mapping:
            missing.append("response_a")
        if not has_response_b:
            missing.append("response_b 또는 llm_output")
    else:
        # pointwise: human_label 필수, conversation 또는 (user_input + llm_output) 필요
        if "human_label" not in mapping:
            missing.append("human_label")
        has_conversation = "conversation" in mapping
        has_turn_pair = "user_input" in mapping and "llm_output" in mapping
        if not has_conversation and not has_turn_pair:
            missing.append("conversation 또는 (user_input + llm_output)")

    return mapping, missing


def derive_task_name(csv_path: str, prompt_path: str | None) -> str:
    """파일 경로에서 task_name을 추론한다."""
    def sanitize(name: str) -> str:
        return name.replace("-", "_").replace(" ", "_").lower()

    if prompt_path:
        p = Path(prompt_path)
        stem = p.stem.lower()
        if stem in GENERIC_FILENAMES:
            parent = p.parent
            if parent.name and parent.name[0] == "v" and parent.name[1:2].isdigit():
                parent = parent.parent
            task_candidate = parent.name
            if task_candidate:
                return sanitize(task_candidate)
        return sanitize(p.stem)

    return sanitize(Path(csv_path).stem)


def load_system_prompt(prompt_path: str | None, task_name: str) -> str:
    """시스템 프롬프트를 읽거나 플레이스홀더를 반환한다."""
    if prompt_path:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read().strip()

    return (
        f"{task_name} 검수 대상 시스템 프롬프트를 여기에 입력하세요.\n"
        "실제 system prompt 전문을 넣어야 Step 1 criteria 품질이 안정적입니다."
    )


def build_config(
    task_name: str,
    system_prompt: str,
    csv_path: str,
    col_mapping: dict[str, str],
    provider: str,
    model: str,
    output_dir: str = "./outputs",
    judge_type: str = "pointwise",
) -> dict:
    """config dict를 구성한다."""
    pointwise_fields = [
        "trace_id", "conversation", "user_input", "llm_output",
        "human_label", "human_reason", "category", "llm_label", "few_shot_type",
    ]
    pairwise_fields = [
        "trace_id", "conversation", "user_input",
        "response_a", "response_b", "llm_output",
        "winner", "human_reason", "category", "few_shot_type",
    ]
    fields = pairwise_fields if judge_type == "pairwise" else pointwise_fields

    columns: dict[str, str] = {}
    for field in fields:
        if field in col_mapping:
            columns[field] = col_mapping[field]

    return {
        "task_name": task_name,
        "judge_type": judge_type,
        "system_prompt": system_prompt,
        "input_csv": csv_path,
        "columns": columns,
        "llm": {
            "provider": provider,
            "model": model,
        },
        "output_dir": output_dir,
    }


def save_config(config: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def default_config_path(task_name: str) -> Path:
    config_root = Path(__file__).parent.parent / "config"
    return config_root / task_name / "config.yaml"


def run(
    csv_path: str,
    prompt_path: str | None,
    output_path: str | None,
    provider: str,
    model: str,
    output_dir: str,
    judge_type: str = "pointwise",
) -> None:
    print(f"[Step 0] CSV 로드: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"  컬럼: {list(df.columns)}")
    print(f"  행 수: {len(df)}")
    print(f"  judge_type: {judge_type}")

    col_mapping, missing_required = detect_columns_verbose(df, judge_type=judge_type)

    print("\n[Step 0] 컬럼 자동 감지 결과:")
    for field, col in col_mapping.items():
        print(f"  {field:15s} -> '{col}'")

    unmapped = [c for c in df.columns if c not in col_mapping.values()]
    if unmapped:
        print(f"  (미매핑 컬럼: {unmapped})")

    if missing_required:
        print(
            f"\n[경고] 필수 컬럼을 감지하지 못했습니다: {missing_required}\n"
            "  생성된 config의 columns 섹션을 직접 수정하세요."
        )

    task_name = derive_task_name(csv_path, prompt_path)
    print(f"\n[Step 0] task_name: {task_name}")

    if prompt_path:
        print(f"[Step 0] 시스템 프롬프트 파일 로드: {prompt_path}")
    else:
        print("[Step 0] --prompt 미제공 -> system_prompt 플레이스홀더를 사용합니다.")
        print("  생성 후 config 파일을 직접 수정하세요.")
    system_prompt = load_system_prompt(prompt_path, task_name)

    config = build_config(
        task_name=task_name,
        system_prompt=system_prompt,
        csv_path=csv_path,
        col_mapping=col_mapping,
        provider=provider,
        model=model,
        output_dir=output_dir,
        judge_type=judge_type,
    )

    if output_path:
        dest = Path(output_path)
    else:
        dest = default_config_path(task_name)

    save_config(config, dest)

    print(f"\n[Step 0] 완료 -> {dest}")
    if missing_required:
        print("\n[주의] 감지되지 않은 필수 컬럼이 있습니다. config를 열어 columns 섹션을 수정하세요.")
    print("\n다음 단계: python pipeline/step1_error_analysis.py --config", dest)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 0: CSV + 시스템 프롬프트 파일로 pipeline config YAML 자동 생성"
    )
    parser.add_argument("--csv", required=True, help="review-interface export CSV 파일 경로")
    parser.add_argument(
        "--prompt",
        default=None,
        help="검수 대상 시스템 프롬프트 파일 경로 (없으면 system_prompt는 플레이스홀더)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="생성할 config YAML 경로 (기본: config/{task_name}/config.yaml)",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai"],
        help="LLM provider (기본: anthropic)",
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-6",
        help="LLM 모델명 (기본: claude-opus-4-6)",
    )
    parser.add_argument(
        "--output-dir",
        default="./outputs",
        help="pipeline 출력 디렉토리 (기본: ./outputs)",
    )
    parser.add_argument(
        "--judge-type",
        default="pointwise",
        choices=["pointwise", "pairwise"],
        help="judge 유형 (기본: pointwise)",
    )
    args = parser.parse_args()
    run(
        csv_path=args.csv,
        prompt_path=args.prompt,
        output_path=args.output,
        provider=args.provider,
        model=args.model,
        output_dir=args.output_dir,
        judge_type=args.judge_type,
    )


if __name__ == "__main__":
    main()
