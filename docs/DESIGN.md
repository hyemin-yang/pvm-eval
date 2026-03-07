# PVM MVP Design

## 목적

`pvm`은 하나의 프로젝트 안에서 여러 프롬프트를 버전 관리하는 도구다.  
최종 형태는 CLI지만, MVP 구현 순서는 다음과 같다.

1. Python 라이브러리로 핵심 도메인 로직 구현
2. 그 위에 CLI를 얇게 포장

이 방식으로 테스트, 재사용성, 확장성을 확보한다.

---

## 핵심 개념

### Project

- 하나의 프로젝트는 현재 디렉토리의 `.pvm/` 디렉토리로 식별한다.
- 프로젝트의 공식 식별자는 `.pvm/config.yaml`에 저장된 `project_id`다.
- `project_id`는 `init` 시 자동 생성되는 ULID다.
- 현재 디렉토리에 `.pvm/`가 없으면 `Not Valid Project`
- `Not Valid Project` 판정은 `.pvm/` 존재만이 아니라 최소 필수 구조 존재 여부까지 확인한다.
- 최소 필수 구조는 `.pvm/config.yaml`, `.pvm/settings/template.yaml`, `.pvm/prompts/`, `.pvm/snapshots/versions/`, `.pvm/snapshots/history.jsonl`이다.
- 부모 디렉토리 탐색은 하지 않는다.

### Prompt

- 하나의 프롬프트는 YAML 템플릿 파일 하나로 정의된다.
- YAML 내부의 `id`가 해당 프롬프트의 유일 식별자다.
- `id`는 사람이 읽기 좋은 식별자이며, 이 프롬프트의 역할 이름으로도 사용한다.
- MVP에서는 `id` 변경을 지원하지 않는다.
- `id`에는 공백과 `/`를 허용하지 않는다.
  - 예: `intent_classifier`, `planner`, `safety_guard`

### Prompt Version

- 각 `id`는 독립적으로 semver(`MAJOR.MINOR.PATCH`) 버전을 가진다.
- `add`는 기본적으로 patch를 증가시킨다.
- `add --minor`, `add --major`로 minor/major 증가를 지원한다.
- 최초 버전은 `0.1.0`이다.

### Production

- `deploy {id} {version}`은 특정 `id`의 현재 production 버전만 변경한다.
- production은 id별로 독립적으로 관리된다.

### Snapshot

- snapshot은 현재 시점의 전체 production 조합을 묶어 저장한 버전이다.
- 즉, `id -> production version` 집합의 스냅샷이다.
- snapshot도 semver를 사용한다.
- `snapshot create`는 기본적으로 patch를 증가시킨다.
- `snapshot create --minor`, `snapshot create --major`를 지원한다.
- snapshot 최초 버전은 `0.1.0`이다.

---

## Prompt YAML 템플릿

MVP 기본 템플릿:

```yaml
id: "intent_classifier"
description: "유저 입력 의도 분류"
author: "alice"

llm:
  provider: "openai"
  model: "gpt-4.1"
  params:
    temperature: 0.2
    max_tokens: 300

prompt: |
  유저 입력을 보고 의도를 분류하라.

input_variables:
  - user_input
  - history
```

### 필수 필드

- `id`
- `llm`
- `prompt`

### 선택 필드

- `description`
- `author`
- `input_variables`

### 템플릿 설계 원칙

- `prompt`는 단일 문자열 프롬프트 본문이다.
- `id`는 별도의 `name` 없이 사람이 읽는 대표 식별자로 사용한다.
- `llm`에는 실제 LLM API/모델 호출에 쓰이는 설정을 저장한다.
- `description`은 사람이 이 프롬프트의 역할을 이해하기 위한 설명이다.
- `author`는 해당 프롬프트를 작성하거나 마지막으로 관리한 사람을 기록한다.
- version별 YAML 원본은 템플릿 스냅샷으로 저장한다.

---

## 내부 저장 구조

```text
.pvm/
  config.yaml
  settings/
    template.yaml
  prompts/
    {id}/
      info.yaml
      production.json
      history.jsonl
      versions/
        0.1.0/
          prompt.md
          model_config.json
          metadata.json
          template.yaml
        0.1.1/
          prompt.md
          model_config.json
          metadata.json
          template.yaml
  snapshots/
    history.jsonl
    versions/
      0.1.0.json
      0.1.1.json
```

---

## 파일별 의미

### `.pvm/config.yaml`

프로젝트 기본 정보 저장.

예시:

```yaml
project_id: "01JNY2V7B6J9M2R4J6FQG7K8TA"
name: "my-pvm-project"
created_at: "2026-03-06T12:00:00Z"
```

### `.pvm/settings/template.yaml`

사용자가 참고할 기본 YAML 템플릿 저장.

### `.pvm/prompts/{id}/info.yaml`

해당 프롬프트의 정적 메타정보 저장.

예시:

```yaml
id: "intent_classifier"
description: "유저 입력 의도 분류"
author: "alice"
created_at: "2026-03-06T12:00:00Z"
```

### `.pvm/prompts/{id}/production.json`

현재 production 버전 저장.

예시:

```json
{
  "id": "intent_classifier",
  "version": "0.1.1",
  "updated_at": "2026-03-06T12:30:00Z"
}
```

### `.pvm/prompts/{id}/history.jsonl`

해당 id의 append-only 이벤트 로그 저장.

### `.pvm/prompts/{id}/versions/{version}/prompt.md`

실제 프롬프트 본문 저장.

### `.pvm/prompts/{id}/versions/{version}/model_config.json`

`llm.provider`, `llm.model`, `llm.params` 저장.

### `.pvm/prompts/{id}/versions/{version}/metadata.json`

버전 생성 정보와 체크섬 저장.

### `.pvm/prompts/{id}/versions/{version}/template.yaml`

사용자가 추가한 원본 YAML 템플릿 스냅샷 저장.

### `.pvm/snapshots/versions/{version}.json`

특정 snapshot의 전체 production 조합 저장.

### `.pvm/snapshots/history.jsonl`

snapshot 생성 이력 저장.

---

## Prompt Version 저장 스키마

### `metadata.json`

예시:

```json
{
  "id": "intent_classifier",
  "version": "0.1.0",
  "description": "유저 입력 의도 분류",
  "author": "alice",
  "created_at": "2026-03-06T12:00:00Z",
  "source_file": "intent_classifier.yaml",
  "prompt_checksum": "sha256...",
  "model_config_checksum": "sha256...",
  "template_checksum": "sha256..."
}
```

### 체크섬 기준

중복 추가 방지를 위해 아래 내용을 정규화 후 체크섬 계산한다.

- `prompt`
- `llm`
- `description`
- `author`

최신 버전과 체크섬이 같으면:

- `No changes` 출력
- 새 버전 생성하지 않음

---

## History 스키마

history는 삭제하지 않는다. append-only 로그로 유지한다.  
롤백도 마지막 기록을 지우는 방식이 아니라 새 이벤트를 추가하는 방식이다.

### Prompt History

경로:

```text
.pvm/prompts/{id}/history.jsonl
```

공통 필드:

- `ts`
- `event`
- `id`

#### `add` 이벤트 예시

```json
{"ts":"2026-03-06T12:00:00Z","event":"add","id":"intent_classifier","version":"0.1.0","template_checksum":"sha256..."}
```

#### `deploy` 이벤트 예시

```json
{"ts":"2026-03-06T12:10:00Z","event":"deploy","id":"intent_classifier","from_version":null,"to_version":"0.1.0"}
```

#### `rollback` 이벤트 예시

```json
{"ts":"2026-03-06T12:20:00Z","event":"rollback","id":"intent_classifier","from_version":"0.1.1","to_version":"0.1.0"}
```

### Snapshot History

경로:

```text
.pvm/snapshots/history.jsonl
```

예시:

```json
{"ts":"2026-03-06T13:00:00Z","event":"create","version":"0.1.0","prompt_count":2}
```

---

## Snapshot 스키마

경로:

```text
.pvm/snapshots/versions/{version}.json
```

예시:

```json
{
  "version": "0.1.0",
  "created_at": "2026-03-06T13:00:00Z",
  "prompt_count": 2,
  "prompts": {
    "intent_classifier": {
      "version": "0.1.0",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    },
    "planner": {
      "version": "0.2.1",
      "prompt_checksum": "sha256...",
      "model_config_checksum": "sha256..."
    }
  }
}
```

### Snapshot 의미

- snapshot은 현재 production 상태를 묶은 집합 버전이다.
- deploy의 부산물이 아니다.
- 사용자가 명시적으로 생성한다.

---

## 도메인 동작 정의

### `init`

- 현재 디렉토리에 `.pvm/` 생성
- 이미 존재하면 방어
- 기본 `config.yaml`, `settings/template.yaml` 생성

### `add`

입력:

- YAML 템플릿 파일 경로

동작:

1. 현재 디렉토리에 `.pvm/` 존재 확인
2. YAML 로드
3. 필수 필드 검증
4. YAML 내부 `id` 추출
5. 해당 `id` 디렉토리 생성 또는 로드
6. 최신 버전 조회
7. bump level에 따라 patch/minor/major 증가
8. 내용 중복 체크
9. 변경 없으면 `No changes` 출력 후 종료
10. 변경 있으면 새 버전 생성
11. history에 `add` 이벤트 기록

### `deploy`

입력:

- `id`
- 선택: `version`

동작:

1. `version`이 없으면 최신 버전 결정
2. 해당 버전 존재 확인
3. 현재 production 읽기
4. 현재 production과 동일 버전이면 no-op
5. `production.json` 갱신
6. history에 `deploy` 이벤트 기록

존재하지 않는 버전이면:

- 아무 일도 하지 않음

현재 production과 동일한 버전이면:

- 아무 일도 하지 않음

### `rollback`

입력:

- `id`

동작:

1. 현재 production 버전 읽기
2. history에서 이전 deploy/rollback 대상 추적
3. 이전 production 버전이 없으면 아무 일도 하지 않음
4. 있으면 `production.json` 갱신
5. history에 `rollback` 이벤트 기록

중요:

- rollback 시 history를 삭제하지 않는다.
- rollback 자체를 새 운영 이벤트로 기록한다.

### `get`

입력:

- `id`
- 선택: `version`

동작:

- `version`이 있으면 해당 버전 프롬프트 반환
- `version`이 없고 production이 있으면 production 프롬프트 반환
- `version`이 없고 production이 없으면 최신 버전 프롬프트 반환

### `diff`

입력:

- `id`
- `from_version`
- `to_version`

동작:

1. 두 버전 디렉토리 존재 확인
2. 각 버전의 `prompt.md`, `model_config.json`, `metadata.json` 읽기
3. `prompt.md` 기준 unified diff 생성
4. `model_config.json` 변경 여부 비교
5. 아래 요약 정보 반환
   - 변경 여부
   - prompt 길이 변화량
   - 추가 줄 수
   - 삭제 줄 수
   - model config 변경 여부
   - checksum 전/후

### `snapshot create`

동작:

1. 현재 모든 `id`의 production 상태 수집
2. bump level에 따라 patch/minor/major 증가
3. snapshot 파일 생성
4. snapshot history 기록

### `snapshot list`

- snapshot 버전 목록 반환

### `snapshot get`

- snapshot 매니페스트 반환
- 즉, `id -> version` 조합과 체크섬 정보 반환

### `snapshot read`

- snapshot이 가리키는 실제 프롬프트 내용을 모두 펼쳐서 반환

예시 반환 개념:

```json
{
  "version": "0.1.0",
  "prompts": {
    "intent_classifier": {
      "version": "0.1.0",
      "llm": {
        "provider": "openai",
        "model": "gpt-4.1",
        "params": {
          "temperature": 0.2,
          "max_tokens": 300
        }
      },
      "prompt": "유저 입력을 보고 의도를 분류하라."
    }
  }
}
```

### `snapshot diff`

- 두 snapshot 간 `id -> version` 조합 차이를 반환
- 추가된 id, 제거된 id, 버전 변경된 id를 구분해 반환
- 버전이 바뀐 id는 후속 prompt diff에 연결할 수 있게 `from_version`, `to_version`을 함께 담는다

---

## 라이브러리 우선 구조

구현은 먼저 라이브러리 형태로 진행한다.

추천 패키지 구조:

```text
pvm/
  __init__.py
  project.py

  core/
    errors.py
    paths.py
    types.py

  config/
    init_project.py
    load_config.py
    load_template.py

  prompts/
    add.py
    deploy.py
    diff.py
    rollback.py
    get.py
    list_ids.py
    get_info.py

  snapshots/
    create.py
    diff.py
    get.py
    list.py
    read.py

  storage/
    checksum.py
    history.py
    json_io.py
    semver.py
    yaml_io.py
```

### `PVMProject` 역할

`PVMProject`는 외부 사용자를 위한 퍼사드 객체다.

예시:

```python
from pvm.project import PVMProject

project = PVMProject.cwd()
project.init(name="my-project")
project.add_prompt("prompt.yaml", bump_level="patch")
project.deploy("intent_classifier")
project.rollback("intent_classifier")
project.get_prompt("intent_classifier")
project.diff_prompt("intent_classifier", "0.1.0", "0.1.1")
project.create_snapshot(bump_level="patch")
project.diff_snapshot("0.1.0", "0.1.1")
snapshot = project.read_snapshot("0.1.0")
```

원칙:

- 외부 API는 `PVMProject` 중심
- 내부 구현은 기능 모듈로 분리
- CLI는 나중에 `PVMProject` 메서드만 호출하는 래퍼로 구현

---

## `Prompt_version_management`에서 가져올 개념

재사용하거나 참고할 핵심 개념:

- YAML 기반 입력
- `id`를 중심으로 한 버전 관리
- 불변 버전 아티팩트 생성
- metadata + checksum 저장
- production 포인터 변경 방식
- diff 가능한 저장 구조

차이점:

- 기존 예제는 `system_prompt` 중심
- `pvm` MVP는 `prompt` 단일 본문 중심
- 기존 예제의 `prod_pointer.json`은 `pvm`에서 id별 `production.json`으로 분리
- 기존 예제의 전체 개념은 `snapshot`으로 확장

---

## CLI 명령 매핑

현재 CLI는 아래 명령으로 제공한다.

- `pvm init`
- `pvm list`
- `pvm project`
- `pvm log`
- `pvm log --id <id>`
- `pvm id <id>`
- `pvm id <id> --info`
- `pvm id <id> --list`
- `pvm template`
- `pvm add <file.yaml>`
- `pvm add <file.yaml> --minor`
- `pvm add <file.yaml> --major`
- `pvm deploy <id>`
- `pvm deploy <id> <version>`
- `pvm rollback <id>`
- `pvm get <id>`
- `pvm get <id> --version <version>`
- `pvm diff <id> <from_version> <to_version>`
- `pvm snapshot create`
- `pvm snapshot create --minor`
- `pvm snapshot create --major`
- `pvm snapshot list`
- `pvm snapshot get <version>`
- `pvm snapshot read <version>`
- `pvm snapshot diff <from_version> <to_version>`

---

## MVP 범위

포함:

- 프로젝트 초기화
- YAML 기반 프롬프트 추가
- semver patch/minor/major 증가
- 동일 내용 중복 추가 방지
- id별 production 관리
- id별 rollback
- prompt diff
- snapshot 생성/조회/읽기
- snapshot diff
- append-only history
- Python 라이브러리 API

제외:

- 부모 디렉토리 프로젝트 탐색
- 복수 템플릿 스키마 자동 매핑
- 고급 validation
- 동시성 락
- 네트워크 배포
- CLI 구현

---

## 구현 단계

MVP 구현은 아래 순서로 진행한다.

### 1. 패키지 골격 구성

- `pvm/` 패키지 생성
- `PVMProject` 퍼사드 추가
- `core`, `config`, `prompts`, `snapshots`, `storage` 폴더 구성
- 공통 예외 타입 정의

구현 방법:

- `pvm/project.py`에 `PVMProject` 클래스를 만든다.
- `PVMProject`는 외부 진입점만 제공하고 내부 구현은 기능 모듈 함수에 위임한다.
- `core/errors.py`에는 `NotValidProjectError`, `AlreadyInitializedError`, `PromptNotFoundError`, `VersionNotFoundError` 같은 예외를 둔다.
- `core/paths.py`에는 `.pvm/`, `prompts/`, `snapshots/` 경로를 계산하는 헬퍼를 둔다.
- 각 기능 폴더는 유스케이스 단위 파일로 나눈다.
  - 예: `prompts/add.py`, `snapshots/create.py`

산출물:

- 기본 import 가능한 라이브러리 구조
- 프로젝트 루트와 `.pvm/` 경로를 다루는 유틸

### 2. 프로젝트 초기화 구현

- `.pvm/` 존재 여부 확인 로직
- `init` 로직 구현
- 기본 파일 생성
  - `config.yaml`
  - `settings/template.yaml`
  - `prompts/`
  - `snapshots/versions/`
  - `snapshots/history.jsonl`

구현 방법:

- `PVMProject.cwd()`는 현재 작업 디렉토리를 root로 갖는 객체를 반환한다.
- `PVMProject.require_valid()` 또는 유사한 내부 메서드에서 최소 필수 `.pvm/` 구조 존재를 검사한다.
- `init`는 현재 디렉토리에 `.pvm/`가 이미 있으면 `AlreadyInitializedError`를 발생시키거나 no-op 정책을 명확히 정한다.
- `init`는 `config.yaml` 생성 시 `project_id`, `name`, `created_at`를 함께 기록한다.
- `project_id`는 ULID로 자동 생성한다.
- 기본 디렉토리는 `mkdir(parents=True, exist_ok=False)`로 생성해 초기화 중복을 방지한다.
- 기본 파일은 템플릿 문자열 또는 딕셔너리를 YAML/JSON으로 직렬화해 쓴다.
- `settings/template.yaml`에는 사용자가 바로 복사해 쓸 수 있는 base prompt 템플릿을 넣는다.
- 초기화가 끝난 뒤에는 최소 필수 구조가 모두 생성되었는지 한 번 더 검증한다.

산출물:

- `PVMProject.init()`
- `PVMProject.cwd()` 또는 현재 디렉토리 프로젝트 로더

### 3. 공통 저장 유틸 구현

- JSON/YAML 읽기/쓰기
- checksum 계산
- semver 증가 로직
- history append 유틸
- timestamp 생성 유틸

구현 방법:

- `storage/json_io.py`에는 JSON load/save 함수, `storage/yaml_io.py`에는 YAML load/save 함수를 둔다.
- 텍스트 저장은 UTF-8 고정으로 처리한다.
- checksum은 `sha256`으로 계산하되, dict는 key 정렬 후 JSON 문자열로 정규화해 해시한다.
- semver 증가는 기본 patch, 선택적 minor/major 증가를 구현한다.
  - 예: `0.1.0 -> 0.1.1`
- history append는 `json.dumps(record, ensure_ascii=False)` 결과를 한 줄씩 append하는 방식으로 구현한다.
- timestamp는 UTC ISO 8601 문자열로 통일한다.

산출물:

- 파일 저장 관련 공통 모듈 완성

### 4. Prompt 추가 기능 구현

- YAML 템플릿 검증
- `id`, `llm`, `prompt`, `description` 추출
- id별 최신 버전 조회
- bump level별 patch/minor/major 증가
- 최신 버전과 checksum 비교
- 동일 내용이면 `No changes` 처리
- 새 버전 디렉토리 생성
  - `prompt.md`
  - `model_config.json`
  - `metadata.json`
  - `template.yaml`
- `history.jsonl`에 `add` 기록

구현 방법:

- `prompts/add.py`에 `add_prompt(root: Path, template_path: Path, bump_level: str = "patch")` 유스케이스 함수를 만든다.
- YAML 로드 후 필수 필드인 `id`, `llm`, `prompt` 존재 여부를 검사한다.
- `author`가 있으면 `info.yaml`, `metadata.json`에 함께 저장한다.
- `id` 디렉토리가 없으면 `info.yaml`, `versions/`, `history.jsonl`를 생성한다.
- 최신 버전은 `versions/` 하위 디렉토리명을 semver로 파싱해서 계산한다.
- 비교용 checksum은 아래 값으로 생성한다.
  - `prompt`
  - `llm`
  - `description`
  - `author`
- 최신 버전의 checksum과 같으면 결과 객체를 `changed=False`로 반환하고 상위 레이어가 `No changes`를 출력하게 한다.
- 새 버전 생성 시:
  - `prompt`는 `prompt.md`
  - `llm`은 `model_config.json`
  - 전체 입력 YAML은 `template.yaml`
  - 요약 메타는 `metadata.json`
- `info.yaml`에는 id와 최초 description 같은 안정적인 메타만 넣고, 버전별 상세는 `metadata.json`에 둔다.
- 마지막에 `history.jsonl`에 `add` 이벤트를 append한다.

산출물:

- `PVMProject.add_prompt(path)`

### 5. Prompt 조회 기능 구현

- 전체 id 목록 조회
- id별 버전 목록 조회
- id 기본 정보 조회
- 특정 버전 또는 현재 production 읽기

구현 방법:

- `prompts/list_ids.py`는 `.pvm/prompts/` 하위 디렉토리 이름을 반환한다.
- `prompts/get_info.py`는 `info.yaml`, `production.json`, 최신 버전 정보를 조합해서 반환한다.
- `prompts/get.py`는 두 모드로 동작한다.
  - `version` 지정 시 해당 버전 디렉토리에서 읽음
  - `version` 미지정 시 `production.json`의 버전을 읽어서 해당 버전 디렉토리에서 읽음
- 반환 형식은 라이브러리에서는 dict 기반으로 통일한다.
- prompt 읽기 결과에는 `id`, `version`, `llm`, `prompt`, `metadata`를 포함시킨다.

산출물:

- `list_prompt_ids()`
- `list_prompt_versions(id)`
- `get_prompt(id, version=None)`
- `get_prompt_info(id)`

### 6. Production 관리 구현

- `deploy(id, version=None)`
- `production.json` 갱신
- `deploy` history 기록
- 없는 버전이면 no-op 후 CLI는 `Version not found`를 출력한다.

- `rollback(id)`
- 이전 deploy/rollback 이력 기반 이전 production 계산
- 이전 production 없으면 no-op
- `rollback` history 기록

구현 방법:

- `prompts/deploy.py`는 먼저 대상 버전 디렉토리 존재 여부를 확인한다.
- 없으면 예외 대신 no-op 결과를 반환한다.
- 있으면 현재 `production.json`을 읽고 이전 버전을 `from_version`으로 잡는다.
- 이후 `production.json`을 새 버전으로 덮어쓴다.
- `history.jsonl`에는 `deploy` 이벤트를 append한다.

- `prompts/rollback.py`는 `history.jsonl`을 뒤에서부터 읽으며 이전 production 후보를 찾는다.
- 기준은 현재 production과 다른 가장 최근의 `to_version`이다.
- 후보가 없으면 no-op 결과를 반환한다.
- 후보가 있으면 `production.json`을 그 버전으로 갱신한다.
- 그 후 `rollback` 이벤트를 append한다.

주의:

- rollback 시 기존 history 레코드는 삭제하지 않는다.
- 운영 이력은 append-only로 유지한다.

산출물:

- `PVMProject.deploy(id, version=None)`
- `PVMProject.rollback(id)`

### 7. Diff 기능 구현

- prompt 버전 간 diff
- snapshot 간 diff

구현 방법:

- `prompts/diff.py`는 `difflib.unified_diff`를 사용해 `prompt.md` 기준 unified diff를 생성한다.
- 줄 수 변화, 추가/삭제 줄 수, checksum 전/후를 함께 계산한다.
- `model_config.json`은 JSON 정규화 후 동일성 비교를 수행한다.
- 반환은 dict 기반으로 통일한다.

- `snapshots/diff.py`는 두 snapshot manifest의 `prompts`를 비교한다.
- 아래 3가지를 구분해 반환한다.
  - `added_ids`
  - `removed_ids`
  - `changed_ids`
- `changed_ids`는 `from_version`, `to_version`을 함께 담는다.

산출물:

- `PVMProject.diff_prompt(id, from_version, to_version)`
- `PVMProject.diff_snapshot(from_version, to_version)`

### 8. Snapshot 기능 구현

- 현재 전체 production 상태 수집
- snapshot semver 증가
- snapshot manifest 생성
- snapshot history 기록
- snapshot 목록 조회
- snapshot 메타 조회
- snapshot 실제 내용 read 구현

구현 방법:

- `snapshots/create.py`는 모든 prompt id를 순회하면서 `production.json`을 읽는다.
- production이 없는 id는 snapshot에서 제외한다.
- 각 production 버전에 대한 `metadata.json`을 함께 읽어 checksum을 manifest에 넣는다.
- snapshot 최신 버전을 기준으로 bump level별 patch/minor/major 증가시켜 새 파일을 만든다.
- 결과는 `.pvm/snapshots/versions/{version}.json`에 저장한다.
- 생성 후 `.pvm/snapshots/history.jsonl`에 `create` 이벤트를 append한다.

- `snapshots/get.py`는 snapshot manifest 파일 자체를 읽어 반환한다.
- `snapshots/list.py`는 `versions/*.json` 파일명을 semver 정렬해 반환한다.
- `snapshots/read.py`는 manifest의 `prompts`를 순회하면서 각 id/version의 실제 `prompt.md`, `model_config.json`, `metadata.json`을 읽어 펼친 결과를 반환한다.

구분:

- `get_snapshot(version)`은 스냅샷 정의 자체를 반환
- `read_snapshot(version)`은 스냅샷이 가리키는 실제 prompt 집합을 반환

산출물:

- `PVMProject.create_snapshot(bump_level="patch")`
- `PVMProject.list_snapshots()`
- `PVMProject.get_snapshot(version)`
- `PVMProject.read_snapshot(version)`

### 9. 테스트 작성

- init 테스트
- add 테스트
  - 첫 버전 생성
  - bump level 지원
  - 동일 내용 no-op
- deploy 테스트
- rollback 테스트
- prompt diff 테스트
- snapshot create/get/read 테스트
- snapshot diff 테스트
- invalid project 테스트

구현 방법:

- 테스트는 임시 디렉토리 기반으로 실행한다.
- 각 테스트는 독립적인 `.pvm/` 프로젝트를 만들고 파일 시스템 결과를 직접 검증한다.
- 단순 return 값만 보지 말고 실제 생성된 파일 내용까지 확인한다.
- rollback 테스트는 최소 2회 deploy 이후 이전 production으로 복귀하는지 검증한다.
- prompt diff 테스트는 prompt 본문 변경과 model config 변경이 모두 감지되는지 검증한다.
- snapshot diff 테스트는 추가/삭제/버전 변경된 id가 정확히 분류되는지 검증한다.
- snapshot read 테스트는 manifest뿐 아니라 실제 prompt 내용이 올바르게 펼쳐지는지 검증한다.

산출물:

- 핵심 유스케이스 회귀 테스트

### 10. CLI 래퍼 추가

라이브러리 API가 안정화된 뒤 CLI를 붙인다.

- `pvm init`
- `pvm add`
- `pvm deploy`
- `pvm rollback`
- `pvm get`
- `pvm diff`
- `pvm snapshot create|get|list|read`
- `pvm snapshot diff`
- `pvm list`, `pvm id`, `pvm log`, `pvm project`, `pvm template`

원칙:

- CLI는 입력 파싱과 출력 formatting만 담당
- 실제 동작은 전부 `PVMProject` 메서드 호출로 처리

구현 방법:

- CLI 엔트리포인트는 별도 모듈에 두고 인자 파싱만 담당하게 한다.
- 각 서브커맨드는 `PVMProject` 메서드 호출 후 결과를 사람이 읽기 쉬운 형태로 출력한다.
- no-op 상황은 예외 대신 메시지로 처리한다.
  - 예: `No changes`, `Version not found`, `No rollback target`
- 라이브러리와 CLI의 책임을 분리하기 위해 출력 문자열 생성은 CLI 레이어에서만 수행한다.

---

## 미정 항목

현재 설계에서 아직 추후 확정 가능한 항목:
