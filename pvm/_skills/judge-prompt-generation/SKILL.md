---
name: judge-prompt-generation
description: |
  Runs the 4-step LLM judge prompt generation pipeline: takes a human-labeled CSV and a registered .pvm prompt, performs error analysis, generates judge criteria and few-shot examples, and executes automated LLM evaluation — saving all outputs under the .pvm versioned store.

  Use this skill whenever the user wants to run or resume the judge pipeline, generate judge prompts from labeled data, analyze LLM failure patterns, or check judge accuracy metrics. Specifically trigger on phrases like "judge 파이프라인 실행", "judge pipeline", "에러 분석하고 judge 프롬프트 만들어줘", "error analysis", "judge prompt 생성", "LLM judge 돌려줘", "자동 평가", "step0/step1/step2/step3 실행", "judge_prompt_generation 파이프라인", "혼동행렬 확인", or "Pass/Fail 비율 봐줘".

  Do not trigger on general requests like "프롬프트 버전 올려줘" (PVM versioning) or "CSV 파일 분석해줘" (general data analysis) that don't involve the judge pipeline.
---

# Judge Prompt Generation Skill

human-labeled CSV와 `.pvm`에 등록된 프롬프트를 입력으로 받아, LLM judge 프롬프트를 자동 생성하고 실행하는 4단계 파이프라인을 관리한다.

```
[CSV + prompt_id]
        ↓
        ↓ 기존 criteria(judge.yaml) 확인 (prompt_id/version 기준)
        ├── 없음 / 재생성 선택
        │        ↓  Step 0: config.yaml 생성 (컬럼 자동 감지, LLM 설정)
        │        ↓  Step 1: error_analysis.json 생성 (실패 패턴 카테고리화)
        │        ↓  Step 2: judge components 생성 (criteria + few-shot → judge.yaml)
        │        ↓  (Criteria 확인 → OK / 수정)
        │        ↓  Step 3: judge_results.json 생성 (trace 단위 LLM 호출)
        │
        └── 기존 criteria 재사용 선택
                 ↓  Step 0: config.yaml 생성 (새 CSV 기준)
                 ↓  기존 judge.yaml 복사 → judge_components/judge.yaml
                 ↓  Step 3: judge_results.json 생성 (trace 단위 LLM 호출)
```

모든 출력물은 `.pvm/prompts/{prompt_id}/versions/{version}/judge/{pipeline_hash}/`에 저장된다.

---

## 인자 처리

### 필수 인자 (없으면 사용자에게 질문)

| 인자 | 설명 |
|------|------|
| `csv` | human-labeled CSV 파일 경로 |
| `prompt_id` | `.pvm`에 등록된 prompt ID |
| `version` | `prompt_id`에서 평가할 prompt version | 

### 선택 인자 (기본값 사용)

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `provider` | `openai` | `openai` / `gemini` / `anthropic` |
| `model` | `gpt-5.4-2026-03-05` | LLM 모델명 |
| `judge-type` | `pointwise` | `pointwise` / `pairwise` |
| `from-step` | `0` | 시작 step 번호 (0~3) |

> ⚠️ **모델 기본값 준수**: `model`은 사용자가 명시하지 않는 한 반드시 `gpt-5.4-2026-03-05`를 사용한다. Claude가 임의로 다른 모델(예: `gpt-4.1`, `gpt-4o` 등)을 지정해서는 안 된다. 스크립트에 `--model` 인자를 넘길 때도 사용자가 명시한 경우에만 해당 값을 사용하고, 명시하지 않았으면 `--model` 인자를 생략하거나 `gpt-5.4-2026-03-05`를 그대로 전달한다.

### 인자 수집 전략

1. `csv` → 메시지에 있으면 바로 사용, 없으면 질문
2. `prompt_id` → 메시지에 있으면 바로 사용. 없으면 `.pvm/prompts/` 하위 디렉토리 목록을 나열하고 사용자가 선택하게 함
   - `.pvm/prompts/` 가 없거나 비어 있으면 "등록된 프롬프트가 없습니다" 안내 후 중단
3. `version` → 명시 없으면 `.pvm/prompts/{prompt_id}/versions/` 디렉토리를 semver 정렬해서 latest 자동 선택
4. `prompt.md` → `prompt_id` + `version` 확정 후 `.pvm/prompts/{id}/versions/{version}/prompt.md` 직접 읽기
5. 나머지는 기본값으로 진행, 사용자가 명시한 값 우선
6. `from-step` → 명시 시 해당 step부터, 없으면 Step 0부터
7. **기존 파이프라인 선택 시 (`from-step` ≥ 1)** → 선택한 `{HASH_DIR}/pipeline_meta.json`에서 `prompt_id`, `prompt_version`, `judge_type`, `model`, `provider` 자동 로드. 항목 1~5 수집 생략

### 파일 유형별 입력 처리

유저가 언급한 파일 유형에 따라 아래 경우의 수를 따른다.

#### 1. yaml 파일만 언급한 경우

해당 yaml 파일을 직접 읽어 pvm에 유효한 형식인지 확인한다.

- **유효한 pvm yaml** (`id`, `llm`, `prompt` 필드 존재) → `id`를 `prompt_id`로 사용해 파이프라인 진행. csv는 별도 질문
- **필수 키 누락** → 누락된 키 목록을 출력하고 사용자에게 값을 재질문:
  ```
  제공하신 yaml 파일에서 다음 필수 항목이 없습니다:
  - id: 이 프롬프트의 고유 ID를 알려주세요
  ```
- **pvm과 무관한 yaml** (judge.yaml, config.yaml 등) → 어떤 용도의 파일인지 사용자에게 확인 후 적절한 처리 (judge.yaml이면 "기존 criteria 재사용 flow" 안내)

#### 2. prompt md 파일만 언급한 경우

`.pvm`에 등록되지 않은 독립 md 파일이므로 `prompt-versioning-manager` 스킬로 먼저 등록한 뒤 파이프라인을 시작한다.

1. **pvm 등록 안내** → "이 파일을 PVM에 먼저 등록하겠습니다" 안내
2. **prompt-versioning-manager 스킬 invoke** → md 파일을 yaml로 변환 후 `pvm add` 실행 (2-A 흐름)
3. 등록 완료 후 → 정상 파이프라인 흐름 진행 (csv는 별도 질문)

#### 3. csv 파일만 언급한 경우

평가 기준이 되는 프롬프트 정보가 없으므로 사용자에게 재질문한다.

```
어떤 프롬프트를 기준으로 평가할까요?
등록된 prompt 목록: (.pvm/prompts/ 하위 디렉토리 나열)

평가할 prompt_id와 version을 알려주세요.
(version 생략 시 latest 자동 선택)
```

- 사용자가 `prompt_id` (+ 선택적 `version`) 입력 → 해당 기준으로 파이프라인 진행
- `.pvm/prompts/` 가 없거나 비어 있으면 → prompt md 파일 또는 yaml을 제공해달라고 안내

---

## 실행 흐름

### Step 0부터 시작할 때

1. **인자 수집** → `csv`, `prompt_id` 확인. 없으면 질문
   - `prompt_id` 확정 직후 **`version`을 즉시 확정** → 명시된 경우 그대로 사용, 없으면 유저에게 질문
   - ⚠️ `version` 확정은 이후 #4(기존 criteria 탐색)에서 `{version}` 경로가 필요하므로 반드시 CSV 등록 전에 완료해야 함
2. **CSV 등록** → `pvm eval register` 실행
   ```bash
   pvm eval register --input {csv_path}
   # stdout 예시:
   # [register] data.csv 복사 완료 → .pvm/datasets/{csv_hash}/data.csv
   # [register] csv_hash: d27f6221dba9f513  rows: 120  columns: ['trace_id', ...]
   # (이미 등록된 경우) [register] 이미 등록된 데이터셋 (csv_hash: {csv_hash})
   # → 마지막 줄의 csv_hash 값을 이후 단계에 사용
   ```
   등록 완료 후 **이후 모든 단계(Step 0 포함)에는 원본 경로가 아닌 `.pvm/datasets/{csv_hash}/data.csv` 절대 경로를 사용한다.**
3. **prompt.md 로드 (자동)** → `.pvm/prompts/{prompt_id}/versions/{version}/prompt.md`
4. **기존 criteria 확인** → `prompt_id/version` 기준으로 `step2`가 완료된 파이프라인이 있는지 확인
   - `.pvm/prompts/{prompt_id}/versions/{version}/judge/` 하위 디렉토리를 순회
   - `pipeline_meta.json`의 `steps_completed`에 `"step2"`가 포함된 항목 수집
   - **있으면** → 목록을 tabulate로 출력 후 사용자에게 선택 요청:
     ```
     이 prompt에 대한 기존 criteria가 있습니다. 어떻게 진행할까요?
     #  | hash         | 생성시각             | CSV 원본 파일명      | judge_type | model
     1  | abc123def456 | 2026-04-10T14:30:00Z | labeled_data.csv     | pointwise  | gpt-5.4-2026-03-05
     2  | ghi789jkl012 | 2026-04-11T09:15:00Z | labeled_data_v2.csv  | pointwise  | claude-opus-4-6
     0. 새로 생성 (Step 1, Step 2 실행)
     ```
   - **없으면** → 새로 생성 흐름으로 진행
5. **분기: 기존 criteria 재사용 vs 새로 생성**
   - **[재사용 선택]** → "기존 criteria 재사용 flow"로 이동 (아래 섹션 참고)
   - **[새로 생성 선택 또는 기존 criteria 없음]** → 6번부터 계속
6. **pipeline_hash 계산 및 디렉토리 준비** → `pvm eval pipeline` 실행
   ```bash
   pvm eval pipeline \
     --csv-hash {csv_hash} \
     --prompt-id {prompt_id} \
     --version {version} \
     --provider {provider} \
     --model {model} \
     --judge-type {judge_type}
   # stdout 예시:
   # [pipeline] pipeline_hash: a3f9c2b1d4e8
   # [pipeline] HASH_DIR: .pvm/prompts/{prompt_id}/versions/{version}/judge/a3f9c2b1d4e8
   # → 두 값을 이후 단계에 사용
   ```
7. **Step 0 실행** → config.yaml 생성. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step0` 실행
8. **(경고 시) 사용자 확인** → 미감지 필수 컬럼 있으면 아래 흐름으로 처리
   1. config 파일 경로(`{HASH_DIR}/config.yaml`)와 수정 방법 안내
   2. **사용자가 config를 수정할 시간을 준 뒤**, "수정을 완료했으면 계속 진행할까요?" 확인 질문
   3. 사용자가 확인 응답 → #9(CSV 컬럼 검증)로 진행
9. **CSV 컬럼 검증** → 아래 "CSV 컬럼 검증" 섹션 기준으로 Step 2 실행 전 검증
10. **Step 1 실행** → LLM 에러 분석. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step1` 실행
11. **Step 2 실행** → judge 프롬프트 조합. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step2` 실행
12. **Criteria 확인** → `{HASH_DIR}/judge_prompt.md` 내용 출력 → 사용자 OK/수정 대기
    - OK → Step 3 실행
    - 수정 요청 시 → 수정 내용 받아 `{HASH_DIR}/judge_components/judge.yaml`의 `criteria` 필드 업데이트 → Step 3 실행
13. **Step 3 실행** → judge 직접 실행. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step3` 실행
14. **결과 요약** → `pvm eval results --run-dir {HASH_DIR}` (`rich` 기반 컬러 테이블)

### 기존 criteria 재사용 flow

기존 `judge.yaml`을 선택하고 새 CSV로 바로 평가를 진행한다. Step 1, Step 2를 건너뛴다.

> **`provider` / `model` / `judge_type` 결정 규칙**: 사용자가 명시한 경우 그 값을 사용. 명시하지 않은 경우 선택한 기존 파이프라인의 `pipeline_meta.json`에서 자동 상속. `judge_type`은 기존 criteria와 반드시 일치해야 하므로 항상 상속 우선.

1. **pipeline_hash 계산 및 디렉토리 준비** → `pvm eval pipeline` 실행 (새 csv_hash 기준으로 새 pipeline_hash 생성)
   ```bash
   pvm eval pipeline \
     --csv-hash {csv_hash} \
     --prompt-id {prompt_id} \
     --version {version} \
     --provider {provider} \
     --model {model} \
     --judge-type {judge_type}
   # 출력: pipeline_hash, HASH_DIR
   ```
2. **Step 0 실행** → 새 CSV 기준으로 config.yaml 생성. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step0` 실행
3. **judge.yaml 복사** → 선택한 기존 파이프라인의 `judge_components/judge.yaml`을 새 HASH_DIR에 복사
   ```bash
   mkdir -p {HASH_DIR}/judge_components
   cp {SOURCE_HASH_DIR}/judge_components/judge.yaml {HASH_DIR}/judge_components/judge.yaml
   ```
4. **step1, step2 완료 표시** → `pvm eval mark-step` 실행
   ```bash
   pvm eval mark-step --run-dir {HASH_DIR} --step step1
   pvm eval mark-step --run-dir {HASH_DIR} --step step2
   ```
5. **Criteria 미리보기** → 복사된 `{HASH_DIR}/judge_components/judge.yaml`의 criteria 내용을 출력하여 사용자에게 확인
   - OK → Step 3 실행
   - 수정 요청 시 → 수정 내용 받아 `judge_components/judge.yaml`의 `criteria` 필드 업데이트 → Step 3 실행
6. **Step 3 실행** → judge 직접 실행. 완료 후 `pvm eval mark-step --run-dir {HASH_DIR} --step step3` 실행
7. **결과 요약** → `pvm eval results --run-dir {HASH_DIR}`

### Step 1~3부터 시작할 때 (`from-step` ≥ 1)

> **필수 선행 조건**: `prompt_id`(+선택적 `version`)가 없으면 파이프라인 목록 탐색 자체가 불가능하므로 반드시 먼저 수집해야 한다. 이 인자들이 없으면 시작 불가 → 질문 후 확정.

1. **`prompt_id` / `version` 수집** → 메시지에 있으면 바로 사용, 없으면 질문. `version` 미제공 시 latest 자동 선택
2. `.pvm/prompts/{prompt_id}/versions/{version}/judge/` 하위 디렉토리 확인
   - **없으면** → Step 0부터 새로 시작 안내
   - **있으면** → 각 `pipeline_meta.json` + `datasets/{csv_hash}/meta.json` 읽어 tabulate 출력
     ```
     #  | hash         | 생성시각             | CSV 원본 파일명      | judge_type | 완료된 steps               | model
     1  | abc123def456 | 2026-04-10T14:30:00Z | labeled_data.csv     | pointwise  | step0, step1, step2, step3 | gpt-5.4-2026-03-05
     2  | ghi789jkl012 | 2026-04-11T09:15:00Z | labeled_data_v2.csv  | pointwise  | step0, step1               | claude-opus-4-6
     0. 새로 시작 (step 0부터)
     ```
3. 선택한 `{HASH_DIR}/pipeline_meta.json`에서 메타 자동 로드
4. 선택한 step에 필요한 파일 존재 확인 후 실행

| 시작 step | 확인 파일 | 없을 때 |
|----------|-----------|---------|
| Step 1 | `config.yaml` | Step 0부터 새로 시작 안내 |
| Step 2 | `config.yaml`, `error_analysis.json` | Step 1 먼저 실행 안내 |
| Step 3 | `config.yaml`, `judge_components/judge.yaml` | Step 2 먼저 실행 안내 |

> **참고:** `from-step 3`을 명시하거나 step2가 완료된 기존 파이프라인을 선택하면 criteria 재사용 확인 없이 바로 Step 3으로 진입한다. criteria 재사용 확인은 **Step 0부터 시작할 때**에만 발생한다.

---

## pvm eval 명령어 레퍼런스

> 실행 디렉토리: **프로젝트 루트** 기준 (`.pvm/`이 있는 곳)

### 사전 준비

```bash
# 1. CSV/xlsx 데이터셋 등록 → csv_hash 획득
pvm eval register --input {csv_or_xlsx_path}
# 필수: --input  (xlsx, xls, csv 모두 지원)
# stdout:
#   [register] data.csv 복사 완료 → .pvm/datasets/{csv_hash}/data.csv
#   [register] csv_hash: d27f6221dba9f513  rows: 120  columns: ['trace_id', ...]
#   (이미 등록된 경우) [register] 이미 등록된 데이터셋 (csv_hash: {csv_hash})

# 2. pipeline 디렉토리 및 pipeline_meta.json 초기 생성 → HASH_DIR 획득
pvm eval pipeline \
  --csv-hash {csv_hash} \
  --prompt-id {prompt_id} \
  --version {version} \
  [--provider openai|gemini|anthropic] \
  [--model {model_name}] \
  [--judge-type pointwise|pairwise]
# 필수: --csv-hash, --prompt-id, --version
# 선택: --provider (기본 openai), --model (기본 gpt-5.4-2026-03-05), --judge-type (기본 pointwise)
# stdout:
#   [pipeline] pipeline_hash: a3f9c2b1d4e8
#   [pipeline] HASH_DIR: .pvm/prompts/{prompt_id}/versions/{version}/judge/a3f9c2b1d4e8
```

### 파이프라인 실행

```bash
HASH_DIR=".pvm/prompts/{prompt_id}/versions/{version}/judge/{pipeline_hash}"

# Step 0: config.yaml 생성 (pipeline_meta.json에서 파라미터 자동 로드)
pvm eval step0 --run-dir {HASH_DIR}
pvm eval mark-step --run-dir {HASH_DIR} --step step0

# Step 1: 에러 분석
pvm eval step1 --run-dir {HASH_DIR}
pvm eval mark-step --run-dir {HASH_DIR} --step step1

# Step 2: judge 프롬프트 생성
pvm eval step2 --run-dir {HASH_DIR}
pvm eval mark-step --run-dir {HASH_DIR} --step step2

# Step 3: judge 실행
pvm eval step3 --run-dir {HASH_DIR}
pvm eval mark-step --run-dir {HASH_DIR} --step step3
```

### 결과 확인 및 이력 조회

```bash
# verdict 분포 + 혼동행렬 출력
pvm eval results --run-dir {HASH_DIR}

# 특정 prompt의 파이프라인 실행 이력 조회
pvm eval runs --prompt-id {prompt_id} [--version {version}]
```

---

## CSV 컬럼 검증 (Step 2 실행 전)

config의 `columns` 섹션 값이 실제 CSV 컬럼에 존재하는지 확인한다. 전체 null 여부도 함께 검증.

### pointwise

| config 키 | 필수 여부 |
|-----------|---------|
| `trace_id` | **필수** |
| `human_label` | **필수** (전체 null 이면 실패) |
| `conversation` | 조건부 필수 (`user_input` + `llm_output` 없을 때) |
| `user_input` | 조건부 필수 (`conversation` 없을 때) |
| `llm_output` | 조건부 필수 (`conversation` 없을 때) |
| `human_reason` | 선택 |

### pairwise

| config 키 | 필수 여부 |
|-----------|---------|
| `trace_id` | **필수** |
| `winner` | **실질적 필수** (없으면 few-shot 예시 0개) |
| `response_a` | **실질적 필수** |
| `response_b` 또는 `llm_output` | **실질적 필수** |
| `user_input` 또는 `conversation` | 조건부 필수 |
| `human_reason` | 선택 |

누락 필수 컬럼 또는 전체 null → 오류 출력 후 중단, config 수정 안내  
누락 선택 컬럼 → 경고 출력 후 계속 진행

---

## 에러 처리 가이드

| 상황 | 동작 | 대응 |
|------|------|------|
| Step 0: 필수 컬럼 자동 감지 실패 | 경고 출력 후 계속 | config 수동 수정 안내 |
| Step 1: 유효 라벨 트레이스 0건 | `ValueError` 중단 | CSV/config 확인 안내 |
| Step 2: `error_analysis.json` 없음 | `sys.exit(1)` | Step 1 먼저 실행 안내 |
| Step 2: `judge_prompt` 카테고리 없음 | 안내 후 정상 종료 | Step 3 건너뜀 안내 |
| Step 3: `judge.yaml` 없음 | `sys.exit(1)` | Step 2 먼저 실행 안내 |
| Step 3: LLM 호출 실패 | `PARSE_ERROR`로 기록 후 계속 | 완료 후 error_count 알림 |

---

## 출력 형식

`show_results.py`는 `rich` 라이브러리 기반 컬러 Panel을 출력한다.

### Panel 1 – Judge verdict 분포 (항상 출력)

```
╭──────────── Judge 평가 결과 ─────────────╮
│ ╭─────────────┬───────┬────────╮         │
│ │ Verdict     │ Count │  Ratio │         │
│ ├─────────────┼───────┼────────┤         │
│ │ Pass        │    74 │  61.7% │  ← 초록 │
│ │ Fail        │    44 │  36.7% │  ← 빨강 │
│ │ PARSE_ERROR │     2 │   1.7% │  ← 노랑 │
│ ├─────────────┼───────┼────────┤         │
│ │ 합계        │   120 │ 100.0% │         │
│ ╰─────────────┴───────┴────────╯         │
╰──────────────────────────────────────────╯
```
- count가 0인 verdict는 행에서 생략됨

### Panel 2 – 혼동행렬 (라벨 있는 트레이스가 있을 때만 출력)

```
╭──────── 혼동행렬  Judge 예측 vs Human 정답 ─────────╮
│ ╭──────────────┬─────────────┬─────────────╮        │
│ │ Judge \ Human│ Human: Pass │ Human: Fail │        │
│ ├──────────────┼─────────────┼─────────────┤        │
│ │ Judge: Pass  │  74  (TP)   │   8  (FP)   │        │
│ │ Judge: Fail  │   7  (FN)   │  29  (TN)   │        │
│ ╰──────────────┴─────────────┴─────────────╯        │
╰────────────────────────────────────────────────────╯
Accuracy 87.3%   Precision 90.2%   Recall 91.4%   F1 90.8%   (라벨 있는 118건 기준)
```
- 라벨 없는 트레이스는 혼동행렬 계산에서 제외됨 (PARSE_ERROR 포함)

### Panel 3, 4 – FP / FN 케이스 상세 (해당 케이스가 있을 때만 출력)

```
╭─── FP  8건  Judge=Pass / Human=Fail ───╮   ← 빨간 테두리
│  trace_id_001                          │
│  trace_id_007                          │
│  ...                                   │
╰────────────────────────────────────────╯

╭─── FN  7건  Judge=Fail / Human=Pass ───╮   ← 노란 테두리
│  trace_id_003                          │
│  trace_id_012                          │
│  ...                                   │
╰────────────────────────────────────────╯
```

### pvm eval mark-step stdout

각 step 완료 후 실행 시 아래 형식으로 출력된다:
```
[mark-step] steps_completed: ['step0']
[mark-step] steps_completed: ['step0', 'step1']
```

---

## .pvm 저장 구조

```
.pvm/
├── datasets/
│   └── {csv_hash}/
│       ├── data.csv                        ← CSV 원본 복사본 (중복 없음)
│       └── meta.json                       ← CSV 등록 정보
└── prompts/
    └── {prompt_id}/
        └── versions/
            └── {version}/
                └── judge/
                    └── {pipeline_hash}/
                        ├── pipeline_meta.json
                        ├── config.yaml
                        ├── error_analysis.json       ← Step 1 출력 (latest)
                        ├── error_analysis_{ts}.json  ← Step 1 스냅샷
                        ├── data_splits.json          ← Step 2 출력
                        ├── data_splits_{ts}.json     ← Step 2 스냅샷
                        ├── judge_components/
                        │   ├── judge.yaml            ← Step 2 출력 (latest)
                        │   └── judge_{ts}.yaml       ← Step 2 스냅샷
                        ├── judge_prompt.md           ← Step 2 미리보기 (Criteria 확인용)
                        ├── judge_prompt_{ts}.md      ← Step 2 미리보기 스냅샷
                        └── judge_results.json        ← Step 3 출력
```

### pipeline_meta.json 스키마

```json
{
  "pipeline_hash": "a3f9c2b1d4e8",
  "prompt_id": "summarize-content",
  "prompt_version": "0.1.0",
  "created_at": "2026-04-10T14:30:00Z",
  "csv_hash": "d27f6221dba9f513",
  "judge_type": "pointwise",
  "provider": "openai",
  "model": "gpt-5.4-2026-03-05",
  "steps_completed": ["step0", "step1", "step2", "step3"]
}
```

`steps_completed`는 각 step 완료 직후 즉시 갱신. 중단 시에도 마지막 갱신 시점까지의 이력 보존.

### datasets/meta.json 스키마

```json
{
  "csv_hash": "d27f6221dba9f513",
  "original_path": "/path/to/labeled.csv",
  "registered_at": "2026-04-10T14:30:00Z",
  "row_count": 120,
  "columns": ["trace_id", "dialogue", "pass_fail", "critique"]
}
```
