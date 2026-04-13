"""
LLM 추상화 레이어 - Anthropic, OpenAI, Gemini를 동일한 인터페이스로 호출.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """단순 system + user 메시지 구조의 단일 LLM 호출 추상화."""

    @abstractmethod
    def call(self, system_prompt: str, user_message: str) -> str:
        """LLM을 호출하고 텍스트 응답을 반환한다."""

    def call_json(self, system_prompt: str, user_message: str) -> Any:
        """LLM을 호출하고 JSON 파싱된 결과를 반환한다."""
        raw = self.call(system_prompt, user_message)
        # 코드 펜스 제거 (```json ... ```)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            cleaned = "\n".join(inner)
        return json.loads(cleaned)


class AnthropicClient(LLMClient):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        thinking_budget: int | None = None,
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic 패키지가 필요합니다: pip install anthropic")

        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = model
        self._thinking_budget = thinking_budget or 0

    def call(self, system_prompt: str, user_message: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 8096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        if self._thinking_budget > 0:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            }
            # max_tokens must exceed thinking_budget
            kwargs["max_tokens"] = max(kwargs["max_tokens"], self._thinking_budget + 2048)

        response = self._client.messages.create(**kwargs)
        # Extended Thinking 응답은 thinking + text 블록으로 구성될 수 있음
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""


class OpenAIClient(LLMClient):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
    ):
        try:
            import openai
        except ImportError:
            raise ImportError("openai 패키지가 필요합니다: pip install openai")

        self._client = openai.OpenAI(
            api_key=api_key or os.environ["OPENAI_API_KEY"]
        )
        self._model = model
        self._reasoning_effort = reasoning_effort or ""

    def call(self, system_prompt: str, user_message: str) -> str:
        # o1/o3 계열은 system role 대신 developer role 사용
        is_reasoning_model = self._model.startswith(("o1", "o3"))
        system_role = "developer" if is_reasoning_model else "system"

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": system_role, "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content


class GeminiClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None):
        try:
            from google import genai
        except ImportError:
            raise ImportError("google-genai 패키지가 필요합니다: pip install google-genai")

        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self._model = model

    def call(self, system_prompt: str, user_message: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]},
            ],
        )
        return response.text or ""


def create_client(llm_config: dict) -> LLMClient:
    """config dict의 provider 값에 따라 적절한 LLMClient를 반환한다.

    Args:
        llm_config: config YAML의 `llm` 섹션 dict.
            예: {"provider": "anthropic", "model": "claude-opus-4-6"}
            예: {"provider": "openai", "model": "gpt-5.4", "reasoning_effort": "medium"}
            예: {"provider": "anthropic", "model": "claude-3-7-sonnet-...", "thinking_budget": 10000}
    """
    provider = llm_config.get("provider", "openai").lower()
    model = llm_config["model"]
    api_key = llm_config.get("api_key")

    if provider == "anthropic":
        return AnthropicClient(
            model=model,
            api_key=api_key,
            thinking_budget=llm_config.get("thinking_budget"),
        )
    elif provider == "openai":
        return OpenAIClient(
            model=model,
            api_key=api_key,
            reasoning_effort=llm_config.get("reasoning_effort"),
        )
    elif provider == "gemini":
        return GeminiClient(model=model, api_key=api_key)
    else:
        raise ValueError(
            f"지원하지 않는 provider: '{provider}'. "
            "'anthropic', 'openai', 'gemini' 중 하나를 사용하세요."
        )
