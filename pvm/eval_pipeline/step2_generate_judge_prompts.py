"""
Step 2: Judge Component 생성

error_analysis.json의 모든 'judge_prompt' 카테고리를 하나의 judge prompt로 합친다.

LLM으로 judge prompt를 새로 생성하지 않는다.
criteria를 통합해 judge_system_prompt.md와 조합 가능한 단일 judge component YAML을 생성한다.

실행:
    python pipeline/step2_generate_judge_prompts.py --config config/my_task.yaml

입력:
    config YAML 파일
    outputs/error_analysis.json (Step 1 출력, 기본값: config의 output_dir 하위)

출력:
    outputs/data_splits.json
    judge_components/{task_name}_judge.yaml
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from judge_composer import FewShotExample, JudgePromptComponents, JudgePromptComposer, save_components
from step1_error_analysis import run as run_error_analysis

RANDOM_SEED = 42
SPLIT_RATIOS = {"train": 0.70, "dev": 0.15, "test": 0.15}


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(config: dict) -> pd.DataFrame:
    config_dir = Path(config.get("_config_dir", "."))
    csv_path = config_dir / config["input_csv"]
    return pd.read_csv(csv_path)


def normalize_label(value: object) -> str:
    text = str(value).strip().lower()
    if text == "pass":
        return "Pass"
    if text == "fail":
        return "Fail"
    # pairwise winner 정규화
    if text == "a":
        return "A"
    if text == "b":
        return "B"
    if text == "same":
        return "SAME"
    return str(value).strip()


def normalize_optional_text(value: object) -> str:
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def normalize_few_shot_type(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"clear_pass", "clear_fail", "borderline_pass", "borderline_fail"}:
        return text
    return ""


def normalize_few_shot_type_pairwise(value: object, winner: str = "") -> str:
    """pairwise 퓨샷 타입 정규화.

    명시적 타입이 없으면 borderline checkbox + winner에서 파생한다.
    """
    text = str(value).strip().lower()
    pairwise_types = {"clear_a", "clear_b", "clear_same", "borderline_a", "borderline_b", "borderline_same"}
    if text in pairwise_types:
        return text
    # 레거시 pointwise borderline 타입에서 pairwise 타입으로 변환
    if text == "borderline_pass" and winner == "SAME":
        return "borderline_same"
    if text in ("borderline_pass", "borderline_fail") and winner == "A":
        return "borderline_a"
    if text in ("borderline_pass", "borderline_fail") and winner == "B":
        return "borderline_b"
    return ""


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


def choose_fewshot_pairwise(row: pd.Series, cols: dict) -> tuple[str, str, str, str]:
    """pairwise few-shot용 prompt, response_a, response_b, conversation을 반환한다."""
    prompt = ""
    user_input_col = cols.get("user_input", "")
    conversation_col = cols.get("conversation", "")
    if user_input_col and user_input_col in row.index:
        prompt = str(row[user_input_col]).strip()
    elif conversation_col and conversation_col in row.index:
        prompt = str(row[conversation_col]).strip()

    response_a_col = cols.get("response_a", "")
    response_b_col = cols.get("response_b", "") or cols.get("llm_output", "")
    response_a = str(row[response_a_col]).strip() if response_a_col and response_a_col in row.index else ""
    response_b = str(row[response_b_col]).strip() if response_b_col and response_b_col in row.index else ""

    return prompt, response_a, response_b, prompt  # conversation = prompt for pairwise


def choose_fewshot_prompt_and_response(row: pd.Series, cols: dict) -> tuple[str, str, str]:
    """few-shot용 prompt/response/conversation을 고른다.

    우선순위:
    1. user_input + llm_output
    2. conversation만 있을 경우 prompt=conversation, response=""
    """
    user_input_col = cols.get("user_input", "")
    llm_output_col = cols.get("llm_output", "")

    prompt = ""
    response = ""
    if user_input_col and user_input_col in row.index:
        prompt = str(row[user_input_col]).strip()
    if llm_output_col and llm_output_col in row.index:
        response = str(row[llm_output_col]).strip()

    if prompt or response:
        parts = []
        if prompt:
            parts.append(prompt)
        if response:
            parts.append(f"[AI] {response}")
        return prompt, response, "\n".join(parts).strip()

    conversation = build_conversation_text(row, cols)

    return conversation, "", conversation


def split_traces(trace_ids: list[str], seed: int = RANDOM_SEED) -> dict[str, list[str]]:
    """trace ID 목록을 train/dev/test로 분할한다."""
    ids = list(trace_ids)
    random.seed(seed)
    random.shuffle(ids)
    n = len(ids)
    n_train = math.ceil(n * SPLIT_RATIOS["train"])
    n_dev = math.ceil(n * SPLIT_RATIOS["dev"])
    return {
        "train": ids[:n_train],
        "dev": ids[n_train:n_train + n_dev],
        "test": ids[n_train + n_dev:],
    }


def select_fewshot_examples(
    category_id: str,
    trace_labels: dict,
    df: pd.DataFrame,
    cols: dict,
    used_trace_ids: set[str] | None = None,
) -> dict[str, dict | None]:
    """human-labeled 데이터 전체에서 few-shot 예시를 선택한다.

    우선순위:
    1. human이 지정한 few_shot_type
    2. llm_label != human_label 이면 borderline_pass / borderline_fail
    3. 없으면 category별 Pass/Fail을 clear_pass / clear_fail로 사용
    """
    trace_id_col = cols["trace_id"]
    human_label_col = cols["human_label"]
    human_reason_col = cols.get("human_reason", "")
    llm_label_col = cols.get("llm_label", "")
    few_shot_type_col = cols.get("few_shot_type", "")

    clear_pass_candidates: list[dict] = []
    clear_fail_candidates: list[dict] = []
    borderline_pass_candidates: list[dict] = []
    borderline_fail_candidates: list[dict] = []

    for _, row in df.iterrows():
        tid = str(row[trace_id_col])

        category_label = trace_labels.get(tid, {}).get(category_id)
        if not category_label:
            continue

        human_label = normalize_label(row[human_label_col])
        if human_label not in {"Pass", "Fail"}:
            continue
        llm_label = normalize_label(row.get(llm_label_col, "")) if llm_label_col else ""
        is_disagreement = bool(llm_label_col and llm_label and llm_label != human_label)
        explicit_few_shot_type = (
            normalize_few_shot_type(row.get(few_shot_type_col, ""))
            if few_shot_type_col
            else ""
        )

        prompt, response, conversation = choose_fewshot_prompt_and_response(row, cols)

        entry = {
            "trace_id": tid,
            "prompt": prompt,
            "response": response,
            "conversation": conversation,
            "human_label": human_label,
            "human_reason": normalize_optional_text(row.get(human_reason_col, "")) if human_reason_col else "",
            "llm_label": llm_label,
            "is_disagreement": is_disagreement,
        }

        if explicit_few_shot_type == "clear_pass":
            clear_pass_candidates.append(entry)
        elif explicit_few_shot_type == "clear_fail":
            clear_fail_candidates.append(entry)
        elif explicit_few_shot_type == "borderline_pass":
            borderline_pass_candidates.append(entry)
        elif explicit_few_shot_type == "borderline_fail":
            borderline_fail_candidates.append(entry)
        elif is_disagreement and category_label == "Pass":
            borderline_pass_candidates.append(entry)
        elif is_disagreement and category_label == "Fail":
            borderline_fail_candidates.append(entry)
        elif category_label == "Pass":
            clear_pass_candidates.append(entry)
        elif category_label == "Fail":
            clear_fail_candidates.append(entry)

    rng = random.Random(RANDOM_SEED)

    global_used = used_trace_ids or set()
    local_used: set[str] = set()

    def pick(candidates: list[dict]) -> dict | None:
        if not candidates:
            return None
        # 1순위: critique 있는 케이스, 2순위: critique 없지만 human 라벨 있는 케이스
        with_critique = [c for c in candidates if c.get("human_reason")]
        base = with_critique if with_critique else candidates
        preferred = [
            c for c in base
            if c["trace_id"] not in global_used and c["trace_id"] not in local_used
        ]
        pool = preferred or [c for c in base if c["trace_id"] not in local_used] or base
        choice = rng.choice(pool)
        local_used.add(choice["trace_id"])
        if used_trace_ids is not None:
            used_trace_ids.add(choice["trace_id"])
        return choice

    return {
        "clear_pass": pick(clear_pass_candidates),
        "clear_fail": pick(clear_fail_candidates),
        "borderline_pass": pick(borderline_pass_candidates),
        "borderline_fail": pick(borderline_fail_candidates),
    }


def select_fewshot_examples_pairwise(
    category_id: str,
    trace_labels: dict,
    df: pd.DataFrame,
    cols: dict,
    used_trace_ids: set[str] | None = None,
) -> dict[str, dict | None]:
    """pairwise 데이터에서 few-shot 예시를 선택한다."""
    trace_id_col = cols["trace_id"]
    winner_col = cols.get("winner", "")
    human_reason_col = cols.get("human_reason", "")
    few_shot_type_col = cols.get("few_shot_type", "")

    buckets: dict[str, list[dict]] = {
        "clear_a": [],
        "clear_b": [],
        "clear_same": [],
        "borderline_a": [],
        "borderline_b": [],
        "borderline_same": [],
    }

    for _, row in df.iterrows():
        tid = str(row[trace_id_col])
        category_label = trace_labels.get(tid, {}).get(category_id)
        if not category_label:
            continue

        winner = normalize_label(row[winner_col]) if winner_col else ""
        if winner not in {"A", "B", "SAME"}:
            continue

        explicit_type = (
            normalize_few_shot_type_pairwise(row.get(few_shot_type_col, ""), winner)
            if few_shot_type_col
            else ""
        )

        prompt, response_a, response_b, conversation = choose_fewshot_pairwise(row, cols)
        entry = {
            "trace_id": tid,
            "prompt": prompt,
            "response_a": response_a,
            "response": response_b,
            "conversation": conversation,
            "winner": winner,
            "human_reason": normalize_optional_text(row.get(human_reason_col, "")) if human_reason_col else "",
        }

        if explicit_type:
            buckets[explicit_type].append(entry)
        elif winner == "A":
            buckets["clear_a"].append(entry)
        elif winner == "B":
            buckets["clear_b"].append(entry)
        elif winner == "SAME":
            buckets["clear_same"].append(entry)

    rng = random.Random(RANDOM_SEED)
    global_used = used_trace_ids or set()
    local_used: set[str] = set()

    def pick(candidates: list[dict]) -> dict | None:
        if not candidates:
            return None
        # 1순위: critique 있는 케이스, 2순위: critique 없지만 human 라벨 있는 케이스
        with_critique = [c for c in candidates if c.get("human_reason")]
        base = with_critique if with_critique else candidates
        preferred = [
            c for c in base
            if c["trace_id"] not in global_used and c["trace_id"] not in local_used
        ]
        pool = preferred or [c for c in base if c["trace_id"] not in local_used] or base
        choice = rng.choice(pool)
        local_used.add(choice["trace_id"])
        if used_trace_ids is not None:
            used_trace_ids.add(choice["trace_id"])
        return choice

    return {key: pick(bucket) for key, bucket in buckets.items()}


def build_criterion_block(category: dict) -> str:
    """개별 error_analysis 카테고리를 단일 criterion 블록으로 변환한다."""
    return (
        f"### {category['name']}\n"
        f"- 정의: {category['definition']}\n"
        f"- 판정 기준: 검수 대상 system prompt를 따르는 응답이 이 실패 모드에 해당하는지 독립적으로 평가하세요.\n"
        f"- Pass: 대화에서 이 실패 모드의 명확한 증거가 없습니다.\n"
        f"- Fail: 대화에서 이 실패 모드에 해당하는 구체적 증거가 확인됩니다.\n"
    )


def build_criterion_block_pairwise(category: dict) -> str:
    """pairwise judge용 criterion 블록. 두 응답 비교 기준으로 서술한다."""
    return (
        f"### {category['name']}\n"
        f"- 정의: {category['definition']}\n"
        f"- 판정 기준: 이 기준에 따라 Response A와 Response B를 비교하세요.\n"
        f"- A 우세: Response A가 이 기준을 Response B보다 더 잘 충족합니다.\n"
        f"- 동등(SAME): 두 응답이 이 기준을 동등하게 충족하거나 차이가 무시할 수 있는 수준입니다.\n"
        f"- B 우세: Response B가 이 기준을 Response A보다 더 잘 충족합니다.\n"
    )


def build_combined_criteria_text(categories: list[dict]) -> str:
    """모든 judge 대상 카테고리를 하나의 criteria 텍스트로 합친다."""
    blocks: list[str] = []
    for category in categories:
        blocks.append(build_criterion_block(category))
        blocks.append("")
    return "\n".join(blocks).strip()


def build_few_shot_components_pairwise(examples: dict[str, dict | None]) -> list[FewShotExample]:
    """pairwise few-shot 예시를 JudgePromptComponents용 객체로 변환한다."""
    result: list[FewShotExample] = []
    for ex_type in ["clear_a", "clear_b", "clear_same", "borderline_a", "borderline_b", "borderline_same"]:
        ex = examples.get(ex_type)
        if not ex:
            continue
        critique = ex.get("human_reason", "").strip() or "수동 비평 없음"
        result.append(
            FewShotExample(
                type=ex_type,
                trace_id=ex["trace_id"],
                prompt=ex.get("prompt", ""),
                response=ex.get("response", ""),       # response_b
                response_a=ex.get("response_a", ""),
                conversation=ex.get("conversation", ""),
                label="",
                winner=ex["winner"],
                critique=critique,
            )
        )
    return result


def _ensure_pairwise_error_analysis(
    config_path: str,
    error_analysis_path: Path,
    judge_type: str,
) -> None:
    if error_analysis_path.exists() or judge_type != "pairwise":
        return
    print(f"[Step 2] {error_analysis_path.name} 없음 -> CSV critique/category 기반으로 criteria 분석을 먼저 생성합니다.")
    run_error_analysis(config_path)


def build_few_shot_components(examples: dict[str, dict | None], category_name: str) -> list[FewShotExample]:
    """few-shot 예시를 JudgePromptComponents용 객체로 변환한다."""
    result: list[FewShotExample] = []

    for ex_type in ["clear_pass", "clear_fail", "borderline_pass", "borderline_fail"]:
        ex = examples.get(ex_type)
        if not ex:
            continue

        critique_parts = []
        if ex.get("human_reason"):
            critique_parts.append(ex["human_reason"])
        if ex.get("is_disagreement") and ex.get("llm_label"):
            critique_parts.append(f"참고: 기존 LLM 판정은 {ex['llm_label']}였습니다.")
        critique = "\n".join(critique_parts).strip() or "수동 비평 없음"

        result.append(
            FewShotExample(
                type=ex_type,
                trace_id=ex["trace_id"],
                prompt=ex.get("prompt", ""),
                response=ex.get("response", ""),
                conversation=ex["conversation"],
                label=ex["human_label"],
                critique=critique,
            )
        )

    return result


def run(
    config_path: str,
    error_analysis_path_override: str | None = None,
    output_dir_override: str | None = None,
) -> None:
    config = load_config(config_path)
    config_path_obj = Path(config_path).resolve()
    config["_config_dir"] = str(config_path_obj.parent)

    cols = config["columns"]
    judge_type = config.get("judge_type", "pointwise")
    system_prompt_text = config.get("system_prompt") or config.get("task_description", "")

    output_dir = Path(config.get("output_dir", "./outputs"))
    if not output_dir.is_absolute():
        output_dir = config_path_obj.parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    components_dir = Path(output_dir_override) if output_dir_override else output_dir / "judge_components"
    components_dir.mkdir(parents=True, exist_ok=True)

    if error_analysis_path_override:
        error_analysis_path = Path(error_analysis_path_override)
    else:
        error_analysis_path = output_dir / "error_analysis.json"

    _ensure_pairwise_error_analysis(config_path, error_analysis_path, judge_type)

    if not error_analysis_path.exists():
        print(f"[오류] {error_analysis_path} 를 찾을 수 없습니다.")
        print("먼저 Step 1을 실행하세요: python pipeline/step1_error_analysis.py --config <config>")
        sys.exit(1)

    with open(error_analysis_path, encoding="utf-8") as f:
        error_analysis = json.load(f)

    categories = error_analysis.get("categories", [])
    trace_labels = error_analysis.get("trace_labels", {})
    all_trace_ids = list(trace_labels.keys())

    judge_categories = [c for c in categories if c.get("action") == "judge_prompt"]
    code_check_categories = [c for c in categories if c.get("action") == "code_check"]
    ignored_categories = [c for c in categories if c.get("action") == "ignore"]

    print(f"[Step 2] 에러 분석 결과 로드 완료 (judge_type: {judge_type})")
    print(f"  통합 judge component 대상 카테고리: {len(judge_categories)}개")
    print(f"  code_check 카테고리: {len(code_check_categories)}개")
    print(f"  ignore 카테고리: {len(ignored_categories)}개")

    if code_check_categories:
        print("\n[안내] 아래 카테고리는 코드 체크 대상으로 남겨둡니다:")
        for cat in code_check_categories:
            print(f"  - {cat['name']}: {cat['definition']}")

    if not judge_categories:
        print("\n[완료] judge component가 필요한 카테고리가 없습니다.")
        return

    splits = split_traces(all_trace_ids)
    splits_path = output_dir / "data_splits.json"
    with open(splits_path, "w", encoding="utf-8") as f:
        json.dump(splits, f, ensure_ascii=False, indent=2)
    splits_snapshot_path = output_dir / f"data_splits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(splits_snapshot_path, "w", encoding="utf-8") as f:
        json.dump(splits, f, ensure_ascii=False, indent=2)
    print(f"\n[Step 2] 데이터 분할 저장 -> {splits_path}")
    print(
        f"  train: {len(splits['train'])}개 / "
        f"dev: {len(splits['dev'])}개 / "
        f"test: {len(splits['test'])}개"
    )
    print("  (참고) few-shot 선택은 split을 사용하지 않고 human-labeled 데이터 전체를 후보로 사용합니다.")

    df = load_csv(config)
    composer = JudgePromptComposer()
    combined_few_shot: list[FewShotExample] = []
    used_trace_ids: set[str] = set()

    print("\n[Step 2] 통합 judge component 생성 시작")

    if judge_type == "pairwise":
        # pairwise: winner 컬럼 정규화
        winner_col = cols.get("winner", "")
        if winner_col and winner_col in df.columns:
            df[winner_col] = df[winner_col].map(normalize_label)

        for cat in judge_categories:
            cat_id = cat["id"]
            print(f"\n  수집 중: [{cat_id}] {cat['name']} (실패율 {cat['failure_rate']*100:.1f}%)")
            examples = select_fewshot_examples_pairwise(
                cat_id, trace_labels, df, cols, used_trace_ids=used_trace_ids
            )
            example_summary = ", ".join(
                f"{k}: {'있음' if v else '없음'}" for k, v in examples.items()
            )
            print(f"    few-shot 예시 선택: {example_summary}")
            combined_few_shot.extend(build_few_shot_components_pairwise(examples))

        criteria_text = "\n".join(
            build_criterion_block_pairwise(cat) for cat in judge_categories
        ).strip()
        components = JudgePromptComponents(
            category_id=f"{config['task_name']}_judge",
            category_name=f"{config['task_name']} 통합 judge",
            judge_type="pairwise",
            system_prompt="",
            criteria=criteria_text,
            few_shot=combined_few_shot,
        )
        preview_text = composer.compose_to_string(
            components,
            reference=system_prompt_text,
            prompt="{prompt}",
            response="{response}",
            baseline_model_response="{baseline_model_response}",
        )
    else:
        # pointwise
        human_label_col = cols["human_label"]
        df[human_label_col] = df[human_label_col].map(normalize_label)

        for cat in judge_categories:
            cat_id = cat["id"]
            print(f"\n  수집 중: [{cat_id}] {cat['name']} (실패율 {cat['failure_rate']*100:.1f}%)")
            examples = select_fewshot_examples(cat_id, trace_labels, df, cols, used_trace_ids=used_trace_ids)
            example_summary = ", ".join(
                f"{k}: {'있음' if v else '없음'}" for k, v in examples.items()
            )
            print(f"    few-shot 예시 선택: {example_summary}")
            combined_few_shot.extend(build_few_shot_components(examples, cat["name"]))

        components = JudgePromptComponents(
            category_id=f"{config['task_name']}_judge",
            category_name=f"{config['task_name']} 통합 judge",
            judge_type="pointwise",
            system_prompt="",
            criteria=build_combined_criteria_text(judge_categories),
            few_shot=combined_few_shot,
        )
        preview_text = composer.compose_to_string(
            components,
            reference=system_prompt_text,
            prompt="{prompt}",
            response="{response}",
        )

    output_path = components_dir / f"{config['task_name']}_judge.yaml"
    save_components(components, output_path)
    # Canonical alias for SKILL.md compatibility (기존 criteria 재사용 flow 등)
    save_components(components, components_dir / "judge.yaml")
    component_snapshot_path = components_dir / f"{config['task_name']}_judge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    save_components(components, component_snapshot_path)
    preview_path = output_dir / f"{config['task_name']}_judge_prompt.md"
    preview_path.write_text(preview_text, encoding="utf-8")
    # Canonical alias (SKILL.md는 judge_prompt.md 기준으로 참조)
    (output_dir / "judge_prompt.md").write_text(preview_text, encoding="utf-8")
    preview_snapshot_path = output_dir / f"{config['task_name']}_judge_prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    preview_snapshot_path.write_text(preview_text, encoding="utf-8")

    print("\n[Step 2] 완료!")
    print(f"  생성된 judge component: {output_path}")
    print(f"  component 스냅샷: {component_snapshot_path}")
    print(f"  미리보기: {preview_path}")
    print(f"  미리보기 스냅샷: {preview_snapshot_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: error_analysis -> 통합 judge component YAML 생성")
    parser.add_argument(
        "--config",
        required=True,
        help="config YAML 파일 경로 (예: config/my_task.yaml)",
    )
    parser.add_argument(
        "--error-analysis",
        default=None,
        help="Step 1 출력 파일 경로 (기본: config의 output_dir/error_analysis.json)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="judge component 출력 디렉터리 (기본: <config_dir>/outputs/judge_components)",
    )
    args = parser.parse_args()
    run(
        args.config,
        error_analysis_path_override=args.error_analysis,
        output_dir_override=args.output_dir,
    )


if __name__ == "__main__":
    main()
