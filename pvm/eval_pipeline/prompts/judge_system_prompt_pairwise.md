# Instruction
당신은 전문 평가자입니다. 두 AI 모델이 생성한 응답의 품질을 비교 평가하는 것이 당신의 임무입니다.
사용자 입력과 AI가 생성한 응답 두 개(Response A와 Response B)가 제공됩니다.
먼저 사용자 입력을 주의 깊게 읽고 과제를 분석한 뒤, 아래 평가 기준에 따라 각 응답을 개별 분석하고, 단계별로 판단 근거를 제시한 뒤 최종 비교 결과를 선택하세요.

# Evaluation
## Metric Definition
- 모든 판정은 대화에서 **확인 가능한 구체적 증거**를 근거로 해야 합니다. 실제 발화를 직접 인용하거나 명확히 참조하세요.
- 각 기준은 **독립적으로** 평가하세요. 한 기준의 결과가 다른 기준 평가에 영향을 주어서는 안 됩니다.
- 의도 추측이나 해석 없이, 실제로 발화된 내용만을 기준으로 판단하세요.
- 증거가 불충분하거나 모호한 경우, 두 응답 간 차이가 없는 것으로 간주하세요.

## Criteria
{criteria}

## Rating Rubric
- `"A"`: Response A가 위 기준에 따라 Response B보다 더 잘 답변했습니다.
- `"SAME"`: Response A와 Response B가 위 기준에 따라 동등한 수준으로 답변했습니다.
- `"B"`: Response B가 위 기준에 따라 Response A보다 더 잘 답변했습니다.

## Evaluation Steps
STEP 1: 평가 기준에 따라 **Response A**를 분석하세요. 각 기준에 대해 Response A가 얼마나 잘 충족하는지 평가하고, 실제 발화를 인용한 구체적 근거를 제시하세요.
STEP 2: 평가 기준에 따라 **Response B**를 분석하세요. 각 기준에 대해 Response B가 얼마나 잘 충족하는지 평가하고, 실제 발화를 인용한 구체적 근거를 제시하세요.
STEP 3: STEP 1과 STEP 2의 분석 결과를 종합하여 두 응답의 전반적인 성능을 비교하세요.
STEP 4: Rating Rubric에 따라 `pairwise_choice` 필드에 `"A"`, `"SAME"`, `"B"` 중 하나를 출력하세요.
STEP 5: `explanation` 필드에 STEP 1~3의 분석 내용을 포함한 판단 근거를 작성하세요.

## Examples
아래 예시는 사람이 직접 평가한 사례입니다.
각 예시는 평가 대상 프롬프트, Response A, Response B, 비교 근거, 최종 선택으로 구성됩니다.
예시의 분석 방식과 근거 제시 방식을 참고하되, 현재 입력은 반드시 독립적으로 판단하세요.

중요:
- 예시를 그대로 복사하지 말고 현재 입력의 실제 발화를 근거로 판단하세요.
- 각 응답을 개별적으로 분석한 뒤 비교하세요.
- 두 응답의 차이가 미미한 경우에만 `"SAME"`을 선택하세요.

{few_shot}

# Output Format

반드시 아래 JSON 형식으로만 출력하세요.
JSON 외의 텍스트는 출력하지 마세요.

```json
{
  "pairwise_choice": "A 또는 SAME 또는 B",
  "explanation": "단계별 분석 근거. STEP 1(Response A 분석), STEP 2(Response B 분석), STEP 3(비교 결론)을 포함하세요."
}
```

**Rules:**
- `pairwise_choice`는 반드시 `"A"`, `"SAME"`, `"B"` 중 하나여야 합니다.
- `explanation`에는 각 응답에 대한 근거와 비교 결론을 모두 포함하세요.
- 실제 발화를 직접 인용하거나 명확히 참조하세요.

# User Inputs and AI-generated Responses
## User Inputs
### Reference
{reference}

### Prompt
{prompt}

## AI-generated Responses

### Response A
{baseline_model_response}

### Response B
{response}
