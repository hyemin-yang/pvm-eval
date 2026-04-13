"""
Judge Prompt Composer

Judge prompt를 3가지 구성 요소로 분리하고 조합하는 파이프라인.

구성 요소:
  - system_prompt : 고정 (judge 역할/출력 형식 등 불변 지시)
  - criteria      : 실패 모드별 가변 (Pass/Fail 정의 등 자주 바뀜)
  - few_shot      : 라벨링 데이터 기반 예시 (데이터 추가 시 갱신)

judge_type:
  - "pointwise"  : 단일 응답을 기준에 따라 Pass/Fail로 평가 (기본값)
  - "pairwise"   : 두 응답(Response A, Response B)을 비교해 A/SAME/B로 평가

사용 예 (pointwise):
    from pipeline.judge_composer import JudgePromptComposer, load_components

    composer = JudgePromptComposer()
    components = load_components("judge_components/my_task_judge.yaml")
    system_msg, user_msg = composer.compose(components, prompt="...", response="...")

사용 예 (pairwise):
    components = load_components("judge_components/my_task_pairwise_judge.yaml")
    # components.judge_type == "pairwise"
    system_msg, user_msg = composer.compose(
        components,
        prompt="...",
        baseline_model_response="...",
        response="...",
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml

# ---------------------------------------------------------------------------
# 기본 system prompt 파일 경로
# ---------------------------------------------------------------------------
_PROMPTS_DIR = Path(__file__).parent / "prompts"

_DEFAULT_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "judge_system_prompt.md"
_DEFAULT_PAIRWISE_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "judge_system_prompt_pairwise.md"


def _load_default_system_prompt(judge_type: str = "pointwise") -> str:
    path = (
        _DEFAULT_PAIRWISE_SYSTEM_PROMPT_PATH
        if judge_type == "pairwise"
        else _DEFAULT_SYSTEM_PROMPT_PATH
    )
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------


@dataclass
class FewShotExample:
    """퓨샷 예시 한 건

    pointwise: label(Pass/Fail) + critique 사용
    pairwise : winner(A/SAME/B) + critique(explanation) + response_a + response(=response_b) 사용
    """

    type: str       # clear_pass | clear_fail | borderline_pass | borderline_fail
    label: str      # pointwise: "Pass" | "Fail"
    critique: str   # pointwise: 비평, pairwise: explanation
    prompt: str = ""
    response: str = ""          # pointwise: 단일 응답 / pairwise: Response B
    conversation: str = ""
    trace_id: str = ""
    winner: str = ""            # pairwise 전용: "A" | "SAME" | "B"
    response_a: str = ""        # pairwise 전용: Response A (baseline)

    def resolved_prompt_response(self) -> tuple[str, str]:
        """prompt/response가 없으면 기존 conversation 필드로 최대한 복원한다."""
        prompt = self.prompt.strip()
        response = self.response.strip()
        if prompt or response:
            return prompt, response

        conversation = self.conversation.strip()
        if not conversation:
            return "", ""
        return conversation, ""

    def to_text(self, index: int, is_english: bool = False) -> str:
        """퓨샷 예시를 텍스트로 변환한다. judge_type에 따라 포맷이 다르다."""
        if self.winner:
            return self._to_text_pairwise(index, is_english)
        return self._to_text_pointwise(index, is_english)

    def _to_text_pointwise(self, index: int, is_english: bool = False) -> str:
        prompt, response = self.resolved_prompt_response()
        result_upper = self.label.strip().upper() or "UNKNOWN"
        title = f"### Example {index}: {result_upper}"
        tid = f" (trace_id: {self.trace_id})" if self.trace_id else ""
        lines = [
            f"{title}{tid}",
            f"User: {prompt}",
            f"Response: {response}",
            f"Critique: {self.critique.strip()}",
            f"Result: {self.label.strip()}",
        ]
        return "\n".join(lines)

    def _to_text_pairwise(self, index: int, is_english: bool = False) -> str:
        prompt, response_b = self.resolved_prompt_response()
        response_a = self.response_a.strip()
        winner_upper = self.winner.strip().upper() or "UNKNOWN"
        title = f"### Example {index}: {winner_upper}"
        tid = f" (trace_id: {self.trace_id})" if self.trace_id else ""
        lines = [
            f"{title}{tid}",
            f"Prompt: {prompt}",
            f"Response A: {response_a}",
            f"Response B: {response_b}",
            f"Explanation: {self.critique.strip()}",
            f"Choice: {self.winner.strip()}",
        ]
        return "\n".join(lines)


@dataclass
class JudgePromptComponents:
    """Judge prompt의 3가지 구성 요소 묶음"""

    criteria: str
    judge_type: Literal["pointwise", "pairwise"] = "pointwise"
    system_prompt: str = ""          # 비어 있으면 judge_type에 맞는 기본 파일 사용
    few_shot: list[FewShotExample] = field(default_factory=list)
    category_id: str = ""
    category_name: str = ""

    def resolved_system_prompt(self) -> str:
        """system_prompt가 비어 있으면 judge_type에 맞는 기본 파일에서 로드."""
        return self.system_prompt or _load_default_system_prompt(self.judge_type)


# ---------------------------------------------------------------------------
# 직렬화 헬퍼
# ---------------------------------------------------------------------------


def _fs_to_dict(ex: FewShotExample) -> dict:
    d: dict = {
        "type": ex.type,
        "trace_id": ex.trace_id,
        "prompt": ex.prompt,
        "response": ex.response,
        "conversation": ex.conversation,
        "label": ex.label,
        "critique": ex.critique,
    }
    if ex.winner:
        d["winner"] = ex.winner
    if ex.response_a:
        d["response_a"] = ex.response_a
    return d


def _fs_from_dict(d: dict) -> FewShotExample:
    return FewShotExample(
        type=d.get("type", ""),
        prompt=d.get("prompt", ""),
        response=d.get("response", ""),
        conversation=d.get("conversation", ""),
        label=d.get("label", ""),
        critique=d.get("critique", ""),
        trace_id=d.get("trace_id", ""),
        winner=d.get("winner", ""),
        response_a=d.get("response_a", ""),
    )


def load_components(path: str | Path) -> JudgePromptComponents:
    """YAML 파일에서 JudgePromptComponents를 로드한다."""
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    few_shot = [_fs_from_dict(ex) for ex in data.get("few_shot", [])]
    return JudgePromptComponents(
        category_id=data.get("category_id", ""),
        category_name=data.get("category_name", ""),
        judge_type=data.get("judge_type", "pointwise"),
        system_prompt=data.get("system_prompt", ""),
        criteria=data.get("criteria", ""),
        few_shot=few_shot,
    )


def save_components(components: JudgePromptComponents, path: str | Path) -> None:
    """JudgePromptComponents를 YAML 파일로 저장한다."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "category_id": components.category_id,
        "category_name": components.category_name,
        "judge_type": components.judge_type,
        "criteria": components.criteria,
        "few_shot": [_fs_to_dict(ex) for ex in components.few_shot],
    }
    # system_prompt가 있을 때만 저장 (없으면 기본 파일 사용)
    if components.system_prompt:
        data["system_prompt"] = components.system_prompt

    with p.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------


class JudgePromptComposer:
    """3가지 구성 요소를 조합해 judge prompt를 만든다.

    Args:
        system_prompt_override: 기본 파일 대신 사용할 system prompt 텍스트.
                                None이면 judge_type에 맞는 기본 파일 사용.
    """

    def __init__(self, system_prompt_override: Optional[str] = None) -> None:
        self._system_prompt_override = system_prompt_override

    # ------------------------------------------------------------------
    # 내부 포매터
    # ------------------------------------------------------------------

    def _is_english_prompt(self, system_prompt: str) -> bool:
        lowered = system_prompt.lower()
        return "## few-shot examples" in lowered or "output exactly the following json" in lowered

    def _format_few_shot(self, few_shot: list[FewShotExample], system_prompt: str = "") -> str:
        if not few_shot:
            return ""
        return "\n\n".join(
            ex.to_text(index=idx)
            for idx, ex in enumerate(few_shot, start=1)
        )

    def _build_system_message(
        self,
        components: JudgePromptComponents,
        reference: str = "",
        prompt: str = "{prompt}",
        response: str = "{response}",
        baseline_model_response: str = "{baseline_model_response}",
        include_few_shot: bool = True,
    ) -> str:
        """system 메시지 텍스트 조합."""
        sp = self._system_prompt_override or components.resolved_system_prompt()
        criteria_text = components.criteria.strip()
        few_shot_text = (
            self._format_few_shot(components.few_shot, system_prompt=sp)
            if include_few_shot and components.few_shot
            else ""
        )

        if "{criteria}" in sp:
            rendered = sp.replace("{criteria}", criteria_text)
            rendered = rendered.replace("{few_shot}", few_shot_text)
            rendered = rendered.replace("{reference}", reference)
            rendered = rendered.replace("{prompt}", prompt)
            rendered = rendered.replace("{baseline_model_response}", baseline_model_response)
            rendered = rendered.replace("{response}", response)
            return rendered.strip()

        # {criteria} 플레이스홀더가 없는 경우 순서대로 붙인다 (레거시 호환)
        parts: list[str] = []
        if sp:
            parts.append(sp)
        if criteria_text:
            parts.append(criteria_text)
        if include_few_shot and components.few_shot:
            section_title = "## Few-shot Examples" if self._is_english_prompt(sp) else "## 예시"
            few_shot_block = section_title + "\n\n" + self._format_few_shot(components.few_shot, system_prompt=sp)
            parts.append(few_shot_block)

        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self,
        components: JudgePromptComponents,
        user_input: str = "",
        reference: str = "",
        prompt: str = "{prompt}",
        response: str = "{response}",
        baseline_model_response: str = "{baseline_model_response}",
        include_few_shot: bool = True,
    ) -> tuple[str, str]:
        """LLM 호출용 (system_message, user_message) 튜플을 반환한다.

        Args:
            components: 3가지 구성 요소
            user_input: 별도 user message가 필요한 경우 사용할 값.
            reference: judge 템플릿의 {reference}에 들어갈 텍스트.
            prompt: judge 템플릿의 {prompt}에 들어갈 텍스트.
            response: judge 템플릿의 {response}에 들어갈 텍스트.
                      pointwise: 평가 대상 응답 / pairwise: Response B
            baseline_model_response: pairwise 전용. {baseline_model_response}에 들어갈 텍스트 (Response A).
            include_few_shot: system_message에 퓨샷 포함 여부 (기본 True)

        Returns:
            (system_message, user_message)
        """
        system_msg = self._build_system_message(
            components,
            reference=reference,
            prompt=prompt,
            response=response,
            baseline_model_response=baseline_model_response,
            include_few_shot=include_few_shot,
        )
        return system_msg, user_input

    def compose_to_string(
        self,
        components: JudgePromptComponents,
        reference: str = "",
        prompt: str = "{prompt}",
        response: str = "{response}",
        baseline_model_response: str = "{baseline_model_response}",
        include_few_shot: bool = True,
    ) -> str:
        """단일 텍스트로 조합한다. 파일 저장 / 미리보기 / 기존 호환용."""
        return self._build_system_message(
            components,
            reference=reference,
            prompt=prompt,
            response=response,
            baseline_model_response=baseline_model_response,
            include_few_shot=include_few_shot,
        )

    def update_criteria(
        self,
        components: JudgePromptComponents,
        new_criteria: str,
    ) -> JudgePromptComponents:
        """criteria만 교체한 새 JudgePromptComponents를 반환한다."""
        from dataclasses import replace
        return replace(components, criteria=new_criteria)

    def update_few_shot(
        self,
        components: JudgePromptComponents,
        new_few_shot: list[FewShotExample],
    ) -> JudgePromptComponents:
        """few_shot만 교체한 새 JudgePromptComponents를 반환한다."""
        from dataclasses import replace
        return replace(components, few_shot=new_few_shot)
