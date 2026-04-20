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
| **라벨링** | LLM 응답 CSV를 업로드해 브라우저에서 Pass/Fail 라벨링 후 labeled CSV로 내보내기 |

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

---

## 빠른 시작

```bash
mkdir my-project && cd my-project
pvm init
pvm ui
```

기본 템플릿 확인:

```bash
pvm template
```

예시 `prompt.yaml`:

```yaml
id: {prompt_id}
description: 사용자 의도를 분류하는 프롬프트
author: alice

llm:
  provider: openai
  model: gpt-5.4

prompt: |
  사용자의 입력을 보고 의도를 분류하세요.
```

프롬프트 추가 → 배포 → 조회 사용 예시:

```bash
pvm add prompt.yaml          # 0.1.0 버전 생성
pvm add prompt.yaml --minor  # 0.2.0
pvm add prompt.yaml --major  # 1.0.0
pvm deploy {prompt_id}
pvm get {prompt_id}
```

---

### API 키 설정

Judge 평가 기능을 사용하려면 Anthropic, OpenAI, 또는 Google Gemini API 키가 필요합니다.

**방법 1 — `.env` 파일 (로컬 개발용)**

프로젝트 작업 디렉토리에 `.env` 파일을 생성합니다.

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

**방법 2 — 웹 UI에서 직접 입력**

서버 실행 후 브라우저에서 사이드바의 **🔑 API Key 설정** 메뉴를 통해 입력할 수 있습니다.  
입력한 키는 `.pvm/api_keys.env`에 저장됩니다.

---

## 사용 방법

프롬프트 추가, 배포, 조회와 이하 기능들은 **웹 UI**, **Claude Skills**, **CLI 명령어** 세 가지 방법으로 이용할 수 있습니다.

---

### 1) 웹 UI

```bash
pvm ui           # 기본 포트 8001
pvm ui --port {포트번호}
```

브라우저에서 `http://127.0.0.1:{포트번호}` 접속.

**지원 기능:**

| 기능 | 설명 |
|---|---|
| 프롬프트 버전 관리 | 버전 추가·배포·롤백·삭제, 버전 간 diff |
| 인라인 에디터 | 브라우저에서 직접 작성 또는 파일 업로드 |
| 라벨링 | LLM 응답 CSV를 업로드해 Pass/Fail 라벨링 후 labeled CSV로 내보내기 |
| LLM Judge 평가 | CSV 업로드 → 에러 분석 → criteria 생성 → Judge 실행 → 리포트 |
| Criteria 직접 편집 | 생성된 criteria를 UI에서 수정 후 저장, 이후 재사용 가능 |
| 실패 사례 조회 | 카테고리별 실패 트레이스를 바로 확인 |
| Criteria 재사용 | 이전 평가에서 생성한 criteria를 불러와 Step 3 바로 실행 |
| A/B 버전 비교 | 두 버전을 동일 데이터로 비교 평가 |
| 평가 이력 관리 | 실행별 Pass Rate·정확도 조회, 삭제 |
| 스냅샷 | 프로젝트 전체 상태 저장·비교 |
| API Key 설정 | `.env` 없이 UI에서 직접 키 입력 |

**LLM Judge 평가 파이프라인 (Step 1 → 3):**

```
Step 1  에러 분석      — 실패 케이스를 카테고리별로 분류, 실패 건수 및 사례 확인
Step 2  Judge 프롬프트 — 카테고리별 criteria 및 통합 Judge 프롬프트 생성, criteria 직접 편집 가능
Step 3  Judge 실행     — 전체 데이터 평가, 정확도·혼동행렬·F1 산출
```

평가에 사용하는 CSV는 LLM 응답에 사람이 직접 Pass/Fail 라벨을 달아둔 데이터입니다.  
위의 **라벨링** 기능으로 만들거나, 직접 작성한 CSV를 업로드할 수 있습니다.  
필수 컬럼은 `trace_id`, `user_input`(또는 `conversation`), `llm_output`, `pass_fail`이며 나머지는 선택입니다.

| 컬럼 | 필수 | 설명 |
|---|:---:|---|
| `trace_id` | ✓ | 트레이스 식별자 |
| `user_input` | ✓ | 사용자 입력 (`conversation` 컬럼으로 대체 가능) |
| `llm_output` | ✓ | 모델 응답 |
| `pass_fail` | ✓ | 사람 레이블 (`Pass` / `Fail`) |
| `critique` | | 사람 판정 이유 — 있으면 Judge few-shot 예시 선정 시 우선 활용 |
| `category` | | 실패 카테고리 — 에러 분석 단계에서 참고용으로 사용 |

---

### 2) Claude Skills

Claude Code에서 `/judge-prompt-generation`, `/prompt-versioning-manager` 스킬을 통해 대화 형태로 파이프라인을 실행할 수 있습니다.

```
/judge-prompt-generation   # Judge 평가 파이프라인 실행
/prompt-versioning-manager # 프롬프트 버전 관리
```

---

### 3) CLI 명령어

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
pvm destroy                    # .pvm/ 디렉토리 전체 삭제 (프로젝트 초기화)
pvm ui                         # 웹 UI 실행
```

---

## Judge 평가 파이프라인 (내부 구조)

평가 파이프라인은 `pvm/eval_pipeline/` 안에 번들되어 있습니다. 별도로 외부 레포를 받을 필요가 없습니다.

```
pvm/eval_pipeline/
├── step0_generate_config.py         # CSV + system prompt → config.yaml
├── step1_error_analysis.py          # 실패 카테고리 도출, 트레이스 라벨링
├── step2_generate_judge_prompts.py  # criteria YAML + Judge 프롬프트 생성
├── step3_run_judge.py               # Judge 실행, 메트릭 산출
├── judge_composer.py                # JudgePromptComposer
├── llm_client.py                    # Anthropic / OpenAI / Gemini 클라이언트
├── pvm_storage.py                   # .pvm/ 디렉토리 구조 관리
└── prompts/                         # 메타 프롬프트 (.md)
```

평가 결과는 `.pvm/prompts/{id}/versions/{ver}/judge/{hash}/` 아래에 저장됩니다.  
업로드한 CSV는 `.pvm/datasets/{hash}/data.csv`에 저장되며, 평가 실행 삭제 시에도 CSV는 유지됩니다.

---

## 데이터 저장 구조

```
.pvm/
├── config.json                        # 프로젝트 설정
├── api_keys.env                       # UI에서 입력한 API 키 (자동 .gitignore 처리)
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
                        │   ├── judge.yaml          # 현재 criteria
                        │   └── *_judge_{ts}.yaml   # 수정·저장된 criteria 이력
                        └── judge_results.json
```

---

## 참고

- Python **3.11** 이상 필요
- 작업 데이터는 현재 디렉토리의 `.pvm/` 아래에 저장
- 첫 버전은 항상 `0.1.0`부터 시작하며, 동일 내용을 추가하면 no-op
- 원본 pvm 설계: [Eumgill98/prompt_versioning_manager](https://github.com/Eumgill98/prompt_versioning_manager)
