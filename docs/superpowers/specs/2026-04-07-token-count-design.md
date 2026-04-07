# Prompt Token Count Feature

## Overview

Prompt detail 페이지에서 OpenAI 모델을 선택하면 해당 prompt의 input token 수를 표시하는 기능.
Local UI와 VS Code extension 모두 동일한 기능을 제공한다.

## Architecture

```
tiktoken (Python) <- pvm core 함수 <- CLI 명령어 <- local UI / VS Code extension
```

단일 CLI 명령어를 통해 local UI와 VS Code extension이 동일한 방식으로 토큰 계산에 접근한다.

## Components

### 1. Core — `pvm/prompts/token_count.py`

두 개의 함수:

```python
def count_tokens(text: str, model: str) -> int:
    """tiktoken으로 주어진 텍스트의 토큰 수를 계산한다."""

def list_supported_models() -> list[str]:
    """tiktoken이 지원하는 모델 목록을 반환한다."""
```

- `tiktoken.encoding_for_model(model)`로 인코딩을 가져와서 `len(encoding.encode(text))`로 계산
- 지원하지 않는 모델이면 에러 반환
- `list_supported_models()`는 tiktoken의 `model.MODEL_TO_ENCODING` 딕셔너리에서 키 목록 추출

### 2. CLI — `pvm token-count`

두 가지 서브커맨드:

```bash
# 토큰 수 계산
pvm token-count <prompt_id> <version> <model>
# 출력: {"model": "gpt-4o", "token_count": 1234}

# 지원 모델 목록
pvm token-count --list-models
# 출력: ["gpt-4o", "gpt-4.1", "gpt-4o-mini", ...]
```

- JSON stdout 출력 (기존 CLI 패턴과 동일)
- prompt_id/version으로 prompt.md를 읽어서 텍스트를 core 함수에 전달

### 3. Local UI

`prompt_detail.html` 페이지에 추가:

- 모델 선택 드롭다운 (페이지 로드 시 지원 모델 목록 세팅)
- 모델 선택 시 AJAX 요청 → 토큰 수 표시
- UI 엔드포인트:
  - `GET /api/token-count/models` → 모델 목록
  - `GET /api/token-count/{prompt_id}/{version}?model=gpt-4o` → 토큰 수

### 4. VS Code Extension

`prompt-detail-panel.ts`에 추가:

- 모델 선택 드롭다운
- 선택 시 `PvmCli`를 통해 CLI 호출 → 결과 표시
- `PvmCli`에 추가할 메서드:
  - `listTokenCountModels(): Promise<string[]>`
  - `countTokens(promptId: string, version: string, model: string): Promise<{model: string, token_count: number}>`

## Dependencies

- `tiktoken`을 `pyproject.toml`의 `[project.dependencies]`에 추가

## Data Flow

```
[User selects model] 
  -> [UI/Extension calls CLI or API endpoint]
  -> [CLI loads prompt.md from disk]
  -> [Core calls tiktoken.encode()]
  -> [Return token count as JSON]
  -> [UI displays count]
```

## Error Handling

- 지원하지 않는 모델 선택 시: 에러 메시지 표시
- prompt가 존재하지 않을 시: 기존 에러 처리 흐름 따름
- tiktoken 미설치 시: CLI에서 에러 메시지 출력

## Scope

- OpenAI 모델만 지원 (tiktoken 기반)
- 읽기 전용 기능 — prompt 데이터 변경 없음
- prompt.md 텍스트만 계산 대상 (model_config, metadata 제외)
