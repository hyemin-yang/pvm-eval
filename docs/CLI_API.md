# CLI

# 프로젝트 관리

## 프로젝트 생성

> `pvm init`

```bash
pvm init                    # 기본 이름 "my-project"
pvm init "custom-project"   # 특정 이름으로 생성
```

- 현재 경로에 `.pvm/` 디렉토리 구조를 생성
- 이미 프로젝트가 존재한다면 에러 발생

---

## 프로젝트 제거

> `pvm destroy`

```bash
pvm destroy          # 확인 프롬프트 표시
pvm destroy --force  # 즉시 삭제
```

- `.pvm/` 디렉토리 전체를 삭제
- 프로젝트가 없다면 에러 발생

---

## 프로젝트 초기화

> `pvm reset`

```bash
pvm reset          # 확인 프롬프트 표시
pvm reset --force  # 즉시 초기화
```

- 모든 프롬프트와 스냅샷 삭제 후 같은 이름으로 재생성
- 기존 프로젝트 이름은 유지

---

## 프로젝트 무결성 체크

> `pvm check`

```bash
pvm check
```

`출력 예제`

```json
{
  "valid": true,
  "missing_dirs": [],
  "missing_files": []
}
```

```json
{
  "valid": false,
  "missing_dirs": [".pvm/settings"],
  "missing_files": [".pvm/settings/template.yaml"]
}
```

---

## 프로젝트 트리 보기

> `pvm project`

```bash
pvm project
```

`출력 예제`

```
project: selectstar-prompt
├── id: intent_classifier
│   ├── version: 0.1.0
│   └── version: 0.2.0 <--- production
└── snapshot: 0.1.0
```

- 프로젝트 이름, 프롬프트 ID/버전, 프로덕션 마커, 스냅샷 목록을 트리 형태로 표시

---

## 기본 템플릿 보기

> `pvm template`

```bash
pvm template
```

`출력 예제`

```yaml
id: intent_classifier
description: Describe the role of this prompt
author: alice
llm:
  provider: openai
  model: gpt-4.1
  params:
    temperature: 0.2
    max_tokens: 300
prompt: Classify the intent of the user input.
input_variables:
- user_input
- history
```

---

# 프롬프트 관리

## 프롬프트 추가

> `pvm add`

```bash
pvm add template.yaml             # patch (기본)
pvm add template.yaml --minor     # minor 버전 증가
pvm add template.yaml --major     # major 버전 증가
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "version": "0.1.0",
  "changed": true
}
```

- YAML 템플릿 파일 경로를 입력으로 받음
- 내용이 동일하면 (SHA-256 체크섬 비교) `No changes` 출력
- `--minor`와 `--major`는 동시 사용 불가

---

## 프롬프트 배포

> `pvm deploy`

```bash
pvm deploy intent_classifier          # 최신 버전 자동 배포
pvm deploy intent_classifier 0.1.0    # 특정 버전 배포
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "version": "0.2.0",
  "changed": true,
  "from_version": "0.1.0"
}
```

- 이미 배포된 버전이면 `Already deployed to production` 출력
- 존재하지 않는 버전이면 `Version not found` 출력

---

## 프롬프트 롤백

> `pvm rollback`

```bash
pvm rollback intent_classifier
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "changed": true,
  "from_version": "0.2.0",
  "to_version": "0.1.0"
}
```

- `production.json`의 `previous_versions` 스택에서 이전 버전을 복원
- 롤백할 대상이 없으면 `No rollback target` 출력

---

## 프롬프트 조회

> `pvm get`

```bash
pvm get intent_classifier                    # 프로덕션 버전 (없으면 최신)
pvm get intent_classifier --version 0.1.0    # 특정 버전
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "version": "0.1.0",
  "llm": {
    "provider": "openai",
    "model": "gpt-4.1",
    "params": {
      "temperature": 0.2,
      "max_tokens": 300
    }
  },
  "prompt": "Classify the intent of the user input.",
  "metadata": {
    "id": "intent_classifier",
    "version": "0.1.0",
    "description": "...",
    "author": "alice",
    "created_at": "2026-04-03T10:30:00Z",
    "source_file": "template.yaml",
    "prompt_checksum": "sha256...",
    "model_config_checksum": "sha256...",
    "template_checksum": "sha256..."
  }
}
```

---

## 프롬프트 상세 조회

> `pvm id`

```bash
pvm id intent_classifier           # 프롬프트 내용 조회
pvm id intent_classifier --info    # 메타데이터 + 버전 요약
pvm id intent_classifier --list    # 버전 목록
```

`--info 출력 예제`

```json
{
  "id": "intent_classifier",
  "info": {
    "id": "intent_classifier",
    "description": "Describe the role of this prompt",
    "author": "alice",
    "created_at": "2026-04-03T10:30:00Z"
  },
  "versions": ["0.1.0", "0.1.1", "0.2.0"],
  "latest_version": "0.2.0",
  "production": {
    "id": "intent_classifier",
    "version": "0.1.1",
    "previous_versions": ["0.1.0"],
    "updated_at": "2026-04-03T11:00:00Z"
  }
}
```

`--list 출력 예제`

```json
["0.1.0", "0.1.1", "0.2.0"]
```

---

## 프롬프트 삭제

> `pvm delete`

```bash
pvm delete intent_classifier          # 확인 프롬프트 표시
pvm delete intent_classifier --force  # 즉시 삭제
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "deleted": true
}
```

- 해당 프롬프트의 모든 버전, 히스토리, 프로덕션 정보가 삭제됨
- 기존 스냅샷에 복사된 파일은 영향 없음
- 없는 ID면 에러 발생

---

## 프롬프트 목록

> `pvm list`

```bash
pvm list                         # 전체 프롬프트 ID 목록
pvm list --id intent_classifier  # 특정 프롬프트 버전 목록
```

`전체 목록 출력 예제`

```json
["intent_classifier", "summarizer", "translator"]
```

`버전 목록 출력 예제`

```json
["0.1.0", "0.1.1", "0.2.0"]
```

---

## 프롬프트 비교

> `pvm diff`

```bash
pvm diff intent_classifier 0.1.0 0.2.0
```

`출력 예제`

```json
{
  "id": "intent_classifier",
  "from_version": "0.1.0",
  "to_version": "0.2.0",
  "changed": true,
  "prompt_length_delta": 42,
  "lines_added": 5,
  "lines_removed": 2,
  "model_config_changed": true,
  "checksum_from": "sha256...",
  "checksum_to": "sha256...",
  "unified_diff": "--- 0.1.0\n+++ 0.2.0\n@@ -1,3 +1,5 @@\n..."
}
```

- 같은 ID 내에서 두 버전을 비교
- `prompt_length_delta` — 프롬프트 텍스트 문자 수 차이
- `lines_added` / `lines_removed` — 추가/삭제된 줄 수
- `model_config_changed` — LLM 설정 변경 여부
- `unified_diff` — unified diff 형식 (변경 없으면 `"(no changes)"`)

---

## 히스토리 보기

> `pvm log`

```bash
pvm log                         # 스냅샷 히스토리
pvm log --id intent_classifier  # 특정 프롬프트 히스토리
```

`출력 예제 (JSONL 원문)`

```
{"ts": "2026-04-03T10:30:00Z", "event": "add", "id": "intent_classifier", "version": "0.1.0", "template_checksum": "sha256..."}
{"ts": "2026-04-03T10:35:00Z", "event": "deploy", "id": "intent_classifier", "from_version": null, "to_version": "0.1.0"}
{"ts": "2026-04-03T11:00:00Z", "event": "rollback", "id": "intent_classifier", "from_version": "0.2.0", "to_version": "0.1.0"}
```

- 프롬프트 이벤트: `add`, `deploy`, `rollback`
- 스냅샷 이벤트: `create`

---

# 스냅샷 관리

## 스냅샷 생성

> `pvm snapshot create`

```bash
pvm snapshot create             # patch (기본)
pvm snapshot create --minor     # minor 버전 증가
pvm snapshot create --major     # major 버전 증가
```

`출력 예제`

```json
{
  "version": "0.1.0",
  "created_at": "2026-04-03T10:30:00Z",
  "snapshot_checksum": "sha256...",
  "prompt_count": 2,
  "prompts": {
    "intent_classifier": {
      "version": "0.2.0",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    },
    "summarizer": {
      "version": "0.1.0",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    }
  }
}
```

- deploy된 프롬프트만 포함
- deploy된 프롬프트가 없으면 스냅샷 생성 안 됨
- `--minor`와 `--major`는 동시 사용 불가

---

## 스냅샷 목록

> `pvm snapshot list`

```bash
pvm snapshot list
```

`출력 예제`

```json
["0.1.0", "0.1.1", "0.2.0"]
```

---

## 스냅샷 매니페스트 조회

> `pvm snapshot get`

```bash
pvm snapshot get 0.1.0
```

`출력 예제`

```json
{
  "version": "0.1.0",
  "created_at": "2026-04-03T10:30:00Z",
  "snapshot_checksum": "sha256...",
  "prompt_count": 2,
  "prompts": {
    "intent_classifier": {
      "version": "0.2.0",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    },
    "summarizer": {
      "version": "0.1.0",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    }
  }
}
```

---

## 스냅샷 전체 읽기

> `pvm snapshot read`

```bash
pvm snapshot read 0.1.0
```

`출력 예제`

```json
{
  "version": "0.1.0",
  "created_at": "2026-04-03T10:30:00Z",
  "prompt_count": 2,
  "prompts": {
    "intent_classifier": {
      "version": "0.2.0",
      "llm": {
        "provider": "openai",
        "model": "gpt-4.1",
        "params": {"temperature": 0.2, "max_tokens": 300}
      },
      "prompt": "Classify the intent of the user input.",
      "metadata": {
        "id": "intent_classifier",
        "version": "0.2.0",
        "description": "...",
        "author": "...",
        "created_at": "...",
        "source_file": "...",
        "prompt_checksum": "sha256...",
        "model_config_checksum": "sha256...",
        "template_checksum": "sha256..."
      }
    },
    "summarizer": {
      "version": "0.1.0",
      "llm": {"...": "..."},
      "prompt": "Summarize the following text.",
      "metadata": {"...": "..."}
    }
  }
}
```

- 스냅샷 내부의 복사된 파일에서 프롬프트 내용을 읽어옴

---

## 스냅샷 비교

> `pvm snapshot diff`

```bash
pvm snapshot diff 0.1.0 0.2.0
```

`출력 예제`

```json
{
  "from_version": "0.1.0",
  "to_version": "0.2.0",
  "added_ids": ["translator"],
  "removed_ids": ["summarizer"],
  "changed_ids": [
    {
      "id": "intent_classifier",
      "from_version": "0.2.0",
      "to_version": "0.3.0"
    }
  ]
}
```

- `added_ids` — 새 스냅샷에 추가된 프롬프트
- `removed_ids` — 이전 스냅샷에서 빠진 프롬프트
- `changed_ids` — 버전이 변경된 프롬프트

---

## 스냅샷 내보내기

> `pvm snapshot export`

```bash
pvm snapshot export 0.1.0                            # 현재 디렉토리에 저장
pvm snapshot export 0.1.0 --output ./my_snapshot.zip  # 경로 지정
```

`출력 예제`

```json
{
  "version": "0.1.0",
  "output_path": "/path/to/project/snapshot-0.1.0.zip"
}
```

`zip 내부 구조`

```
manifest.json
prompts/
  intent_classifier/
    prompt.md
    model_config.json
    metadata.json
  summarizer/
    prompt.md
    model_config.json
    metadata.json
```

---

# UI

## 로컬 웹 UI 실행

> `pvm ui`

```bash
pvm ui              # http://127.0.0.1:8001 + 브라우저 자동 열기
pvm ui --port 9000  # 포트 지정
```

- 로컬 서버를 실행하고 브라우저를 자동으로 열어 웹 UI를 제공
- DB 없이 파일 기반 `.pvm` 프로젝트를 직접 조작
- 프로젝트가 없으면 UI에서 바로 생성 가능
- Judge eval 파이프라인은 패키지에 번들되어 별도 `judge-prompt-generation` 체크아웃이 필요 없음

### UI 기능

| 페이지 | 기능 |
|--------|------|
| Dashboard | 프로젝트 정보, 프로젝트 트리, 프롬프트/스냅샷 요약 |
| Prompts | 프롬프트 목록, 검색 (전체/상세), 상태 필터 |
| Prompt Detail | 버전별 내용 조회, deploy, rollback, delete, diff |
| Add Prompt | Form 입력 / 파일 업로드 / YAML 에디터 |
| Snapshots | 스냅샷 목록, 생성, 비교, export |
| Snapshot Detail | 매니페스트 + 포함된 프롬프트 전체 내용 |
| History | 프롬프트별/스냅샷 이벤트 이력 조회 |
