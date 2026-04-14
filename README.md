# pvm-eval

`pvm-eval`은 로컬에서 프롬프트 버전을 관리하고, 웹 UI에서 버전 비교·LLM Judge 평가·A/B 비교까지 할 수 있는 도구입니다.

> 원본 pvm 설계 및 CLI 구현은 [Eumgill98/prompt_versioning_manager](https://github.com/Eumgill98/prompt_versioning_manager)를 기반으로 합니다.

---

## 주요 기능

| 영역 | 기능 |
|---|---|
| **버전 관리** | 프롬프트 추가·배포·롤백·삭제, 시맨틱 버전(`0.1.0`, `0.2.0`, `1.0.0`) |
| **스냅샷** | 전체 프로젝트 상태를 시점 단위로 저장·비교 |
| **웹 UI** | 프롬프트 목록·diff·배포·평가·비교를 브라우저에서 조작 |
| **LLM Judge 평가** | human-labeled CSV → 에러 분석 → Judge criteria 자동 생성 → Judge 실행 → 정확도/혼동행렬 리포트 |
| **A/B 버전 비교** | 두 프롬프트 버전을 동일 데이터로 나란히 평가해 우열 비교 |
| **Criteria 재사용** | 이미 생성된 Judge criteria를 다른 버전 평가에 그대로 재사용 |

---

## 설치

Python 3.11 이상이 필요합니다.

### pipx (권장)

```bash
# 로컬 클론 후 설치
git clone https://github.com/hyemin-yang/pvm-eval.git
cd pvm-eval/prompt_versioning_manager
pipx install .

# GitHub에서 직접 설치
pipx install "git+https://github.com/hyemin-yang/pvm-eval.git@main#subdirectory=prompt_versioning_manager"
```

### 재설치 (소스 수정 후)

```bash
pipx reinstall pvm
```

### API 키 설정

Judge 평가 기능을 사용하려면 `.env` 파일(또는 환경변수)에 API 키를 설정합니다.

```bash
# 프로젝트 작업 디렉토리에 .env 생성
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

---

## 빠른 시작

```bash
mkdir my-project && cd my-project
pvm init
```

기본 템플릿 확인:

```bash
pvm template
```

예시 `prompt.yaml`:

```yaml
id: intent_classifier
description: 사용자 의도를 분류하는 프롬프트
author: alice

llm:
  provider: openai
  model: gpt-5.4

prompt: |
  사용자의 입력을 보고 의도를 분류하세요.
```

프롬프트 추가 → 배포 → 조회:

```bash
pvm add prompt.yaml          # 0.1.0 버전 생성
pvm add prompt.yaml --minor  # 0.2.0
pvm add prompt.yaml --major  # 1.0.0
pvm deploy intent_classifier
pvm get intent_classifier
```

---

## 자주 쓰는 CLI 명령어

```bash
pvm init                       # 프로젝트 초기화 (.pvm/ 생성)
pvm add <file>                 # 프롬프트 버전 추가
pvm deploy <id>                # 버전을 프로덕션으로 지정
pvm rollback <id>              # 이전 버전으로 롤백
pvm list                       # 프롬프트 목록 조회
pvm list <id>                  # 특정 프롬프트의 버전 목록
pvm get <id>                   # 현재 배포 버전 조회
pvm diff <id>                  # 두 버전 diff
pvm snapshot create            # 전체 프로젝트 스냅샷
pvm project                    # 프로젝트 트리 요약
pvm token-count <id> <ver>     # 프롬프트 토큰 수 계산
pvm delete <id>                # 프롬프트 전체 삭제
pvm ui                         # 웹 UI 실행
```

---

## 웹 UI

프로젝트 디렉토리에서:

```bash
pvm ui
# 기본 포트: 8001
pvm ui --port 9000
```

브라우저에서 `http://127.0.0.1:8001` 접속.

### UI에서 할 수 있는 것

#### 프롬프트 관리
- 프롬프트 목록·버전별 내용 확인
- 버전 간 diff (나란히 비교)
- deploy / rollback 조작
- 개별 버전 삭제 (마지막 버전은 보호)
- 인라인 에디터로 직접 작성 또는 파일 업로드

#### LLM Judge 평가 (3단계 파이프라인)

human-labeled CSV 파일을 업로드하면, LLM이 자동으로 Judge criteria를 만들고 평가를 실행합니다.

```
Step 1  에러 분석     — 실패 케이스를 카테고리별로 분류
Step 2  Judge 프롬프트 — 카테고리별 criteria 및 통합 Judge 프롬프트 생성
Step 3  Judge 실행    — 전체 데이터 평가, 정확도·혼동행렬·F1 산출
```

- **Pass Rate** (Judge가 Pass로 판정한 비율)와 **정확도** (Judge↔Human 일치율)를 메인 지표로 표시
- 혼동 행렬(TP/FP/FN/TN), Precision, Recall, F1 Score 제공
- 트레이스별 결과 테이블 — 행 클릭 시 Judge 판정 상세 전개
- **Criteria 재사용**: 동일 프롬프트의 다른 버전, 또는 재평가 시 기존에 생성한 criteria를 그대로 가져와 Step 1·2를 건너뛰고 바로 Step 3 실행
- 평가 이력 관리 — 실행별 삭제 가능 (CSV 데이터는 보존)

CSV 컬럼 형식:

| 컬럼 | 설명 |
|---|---|
| `trace_id` | 트레이스 식별자 |
| `user_input` | 사용자 입력 |
| `llm_output` | 모델 응답 |
| `pass_fail` | 사람 레이블 (`Pass` / `Fail`) |
| `critique` | 사람 판정 이유 (선택) |
| `category` | 실패 카테고리 (선택) |

#### A/B 버전 비교

두 프롬프트 버전의 응답을 동일 Judge로 나란히 평가해 우열을 비교합니다.

- 동일 프롬프트의 두 버전(A·B)을 선택
- 기존 평가 데이터 재활용 또는 새 CSV 업로드
- Judge 모델 선택 후 3단계 파이프라인 동일하게 실행
- 리포트: A 승 / 동점 / B 승 비율 카드 + 트레이스별 필터

#### 스냅샷
- 전체 프로젝트 상태를 시점 단위로 저장
- 스냅샷 간 diff 비교

---

## Judge 평가 파이프라인 (내부 구조)

평가 파이프라인은 `pvm/eval_pipeline/` 안에 번들되어 있습니다. 별도로 외부 레포를 받을 필요가 없습니다.

```
pvm/eval_pipeline/
├── step0_generate_config.py    # CSV + system prompt → config.yaml
├── step1_error_analysis.py     # 실패 카테고리 도출, 트레이스 라벨링
├── step2_generate_judge_prompts.py  # criteria YAML + Judge 프롬프트 생성
├── step3_run_judge.py          # Judge 실행, 메트릭 산출
├── judge_composer.py           # JudgePromptComposer
├── llm_client.py               # Anthropic / OpenAI 클라이언트
├── pvm_storage.py              # .pvm/ 디렉토리 구조 관리
└── prompts/                    # 메타 프롬프트 (.md)
```

평가 결과는 `.pvm/prompts/{id}/versions/{ver}/judge/{hash}/` 아래에 저장됩니다.  
업로드한 CSV는 `.pvm/datasets/{hash}/data.csv`에 저장되며, 평가 실행 삭제 시에도 CSV는 유지됩니다.

---

## 데이터 저장 구조

```
.pvm/
├── config.json                        # 프로젝트 설정
├── datasets/
│   └── {csv_hash}/
│       ├── data.csv
│       └── meta.json
└── prompts/
    └── {prompt_id}/
        └── versions/
            └── {version}/
                ├── prompt.yaml
                └── judge/
                    └── {pipeline_hash}/
                        ├── error_analysis.json
                        ├── judge_components/
                        └── judge_results.json
```

---

## 참고

- Python **3.11** 이상 필요
- 작업 데이터는 현재 디렉토리의 `.pvm/` 아래에 저장
- 첫 버전은 항상 `0.1.0`부터 시작하며, 동일 내용을 추가하면 no-op
- 원본 pvm 설계: [Eumgill98/prompt_versioning_manager](https://github.com/Eumgill98/prompt_versioning_manager)
