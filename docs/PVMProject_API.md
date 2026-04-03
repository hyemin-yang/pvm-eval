# PVMProject API Reference

`PVMProject`는 pvm의 모든 기능을 제공하는 파사드 클래스입니다.
CLI 없이 Python 코드에서 직접 사용할 수 있습니다.

---

## 인스턴스 생성

```python
from pvm import PVMProject

# 현재 작업 디렉토리 기준
project = PVMProject.cwd()

# 특정 경로 지정 (Path 또는 str)
project = PVMProject(Path("/path/to/project"))
project = PVMProject("/path/to/project")
```

---

## 프로젝트 관리

### `init(name="my-project") -> dict`

`.pvm/` 디렉토리 구조를 생성하고 프로젝트를 초기화합니다.
이미 존재하면 `AlreadyInitializedError`가 발생합니다.

```python
project.init("selectstar-prompt")
# {"project_id": "01J...", "name": "selectstar-prompt", "created_at": "...", "root": "..."}
```

### `destroy() -> dict`

`.pvm/` 디렉토리 전체를 삭제합니다. 프로젝트 루트는 유지됩니다.
유효하지 않은 프로젝트이면 `NotValidProjectError`가 발생합니다.

```python
project.destroy()
# {"destroyed": True, "root": "/path/to/project"}
```

### `reset() -> dict`

프로젝트를 삭제하고 같은 이름으로 재초기화합니다.
`project_id`는 새로 발급되며, 모든 프롬프트와 스냅샷은 삭제됩니다.
`config.yaml`이 깨져서 이름을 읽을 수 없으면 기본값 `"my-project"`로 폴백합니다.

```python
project = PVMProject.cwd()
project.init("selectstar-prompt")

# 프롬프트 추가 & 배포
project.add_prompt("template.yaml")
project.deploy("intent_classifier")

# 상태 확인
print(project.load_config()["name"])    # "selectstar-prompt"
print(project.list_prompt_ids())        # ["intent_classifier"]

# 초기화
project.reset()

# 이름 유지, 데이터 초기화
print(project.load_config()["name"])    # "selectstar-prompt"
print(project.list_prompt_ids())        # []
```

### `is_valid() -> bool`

현재 루트에 유효한 `.pvm/` 레이아웃이 존재하는지 확인합니다.

```python
project.is_valid()
# True / False
```

### `check_integrity() -> dict`

누락된 디렉토리/파일을 상대경로로 알려줍니다.

```python
# 정상
project.check_integrity()
# {"valid": True, "missing_dirs": [], "missing_files": []}

# 깨진 상태
project.check_integrity()
# {"valid": False, "missing_dirs": [".pvm/settings"], "missing_files": [".pvm/settings/template.yaml"]}
```

### `require_valid() -> None`

유효하지 않은 프로젝트이면 `NotValidProjectError`를 발생시킵니다.
`init`을 제외한 모든 메서드에서 내부적으로 호출됩니다.

- `.pvm/`이 없는 경우: `"No pvm project found: ... Initialize a new project first."`
- `.pvm/`은 있지만 깨진 경우: `"Project is corrupted: ... Run integrity check to inspect missing items, or reset the project to re-initialize."`

### `load_config() -> dict`

`.pvm/config.yaml`을 읽어 프로젝트 메타데이터를 반환합니다.

```python
project.load_config()
# {"project_id": "01J...", "name": "selectstar-prompt", "created_at": "2026-04-03T10:30:00Z"}
```

### `load_template() -> dict`

`.pvm/settings/template.yaml`의 기본 프롬프트 템플릿을 반환합니다.

```python
project.load_template()
# {"id": "intent_classifier", "description": "...", "author": "alice", "llm": {...}, "prompt": "...", "input_variables": [...]}
```

---

## 프롬프트 관리

### `add_prompt(template_path, bump_level="patch") -> dict`

YAML 템플릿 파일을 읽어 새로운 불변 버전을 생성합니다.
내용이 동일하면(SHA-256 체크섬 비교) 새 버전을 생성하지 않습니다.

- `template_path`: YAML 템플릿 파일 경로 (`str | Path`)
- `bump_level`: `"patch"` | `"minor"` | `"major"`

**YAML 필수 필드:** `id`, `llm`(dict), `prompt`(str)
**선택 필드:** `description`, `author`, `input_variables` 등 (있으면 저장, 없어도 에러 없음)

```python
# 최초 추가
project.add_prompt("template.yaml")
# {"id": "intent_classifier", "version": "0.1.0", "changed": True}

# 내용 변경 후 patch
project.add_prompt("template_v2.yaml")
# {"id": "intent_classifier", "version": "0.1.1", "changed": True}

# minor / major
project.add_prompt("template_v3.yaml", bump_level="minor")
# {"id": "intent_classifier", "version": "0.2.0", "changed": True}

project.add_prompt("template_v4.yaml", bump_level="major")
# {"id": "intent_classifier", "version": "1.0.0", "changed": True}

# 동일한 내용으로 추가 시도
project.add_prompt("template_v4.yaml")
# {"id": "intent_classifier", "changed": False, "reason": "no_changes"}
```

### `deploy(prompt_id, version=None) -> dict`

특정 버전을 프로덕션으로 배포합니다. `version`이 None이면 최신 버전을 자동 선택합니다.
deploy 시 현재 버전이 `production.json`의 `previous_versions` 스택에 push됩니다.

```python
# 최신 버전 자동 배포
project.deploy("intent_classifier")
# {"id": "intent_classifier", "version": "0.2.0", "changed": True, "from_version": "0.1.0"}

# 특정 버전 배포
project.deploy("intent_classifier", "0.1.0")
# {"id": "intent_classifier", "version": "0.1.0", "changed": True, "from_version": "0.2.0"}

# 이미 배포된 버전
project.deploy("intent_classifier", "0.1.0")
# {"id": "intent_classifier", "version": "0.1.0", "changed": False, "reason": "already_deployed"}

# 최초 배포
project.deploy("intent_classifier")
# {"id": "intent_classifier", "version": "0.1.0", "changed": True, "from_version": None}
```

### `rollback(prompt_id) -> dict`

`production.json`의 `previous_versions` 스택에서 pop하여 이전 프로덕션 버전으로 롤백합니다.

```python
# deploy 1 → 2 → 3 후
project.rollback("intent_classifier")
# {"id": "intent_classifier", "changed": True, "from_version": "0.3.0", "to_version": "0.2.0"}

project.rollback("intent_classifier")
# {"id": "intent_classifier", "changed": True, "from_version": "0.2.0", "to_version": "0.1.0"}

# 스택 비어있음
project.rollback("intent_classifier")
# {"id": "intent_classifier", "changed": False, "reason": "no_rollback_target"}
```

### `get_prompt(prompt_id, version=None) -> dict`

프롬프트 내용을 조회합니다.

**버전 결정 우선순위:**
1. `version` 지정 → 해당 버전
2. 미지정 + 프로덕션 배포됨 → 프로덕션 버전
3. 미지정 + 프로덕션 없음 → 최신 버전

```python
project.get_prompt("intent_classifier")
project.get_prompt("intent_classifier", version="0.1.0")
# {
#     "id": "intent_classifier",
#     "version": "0.1.0",
#     "llm": {
#         "provider": "openai",
#         "model": "gpt-4.1",
#         "params": {"temperature": 0.2, "max_tokens": 300}
#     },
#     "prompt": "Classify the intent of the user input.",
#     "metadata": {
#         "id": "intent_classifier",
#         "version": "0.1.0",
#         "description": "Describe the role of this prompt",
#         "author": "alice",
#         "created_at": "2026-04-03T10:30:00Z",
#         "source_file": "template.yaml",
#         "prompt_checksum": "sha256...",
#         "model_config_checksum": "sha256...",
#         "template_checksum": "sha256..."
#     }
# }
```

### `get_prompt_info(prompt_id) -> dict`

프롬프트의 메타데이터와 버전 요약 정보를 반환합니다.

```python
project.get_prompt_info("intent_classifier")
# {
#     "id": "intent_classifier",
#     "info": {
#         "id": "intent_classifier",
#         "description": "Describe the role of this prompt",
#         "author": "alice",
#         "created_at": "2026-04-03T10:30:00Z"
#     },
#     "versions": ["0.1.0", "0.1.1", "0.2.0"],
#     "latest_version": "0.2.0",
#     "production": {
#         "id": "intent_classifier",
#         "version": "0.1.1",
#         "previous_versions": ["0.1.0"],
#         "updated_at": "2026-04-03T11:00:00Z"
#     }
# }

# deploy 안 한 경우
# { ..., "production": None }
```

### `list_prompt_ids() -> list[str]`

프로젝트 내 모든 프롬프트 ID를 정렬하여 반환합니다.

```python
project.list_prompt_ids()
# ["intent_classifier", "summarizer", "translator"]
```

### `list_prompt_versions(prompt_id) -> list[str]`

특정 프롬프트의 모든 버전을 semver 순으로 반환합니다.

```python
project.list_prompt_versions("intent_classifier")
# ["0.1.0", "0.1.1", "0.2.0"]
```

### `delete_prompt(prompt_id) -> dict`

프롬프트와 모든 버전을 완전히 삭제합니다.
기존 스냅샷에 복사된 파일은 영향 없습니다.

```python
project.list_prompt_ids()
# ["intent_classifier"]

project.delete_prompt("intent_classifier")
# {"id": "intent_classifier", "deleted": True}

project.list_prompt_ids()
# []
```

### `diff_prompt(prompt_id, from_version, to_version) -> dict`

같은 프롬프트의 두 버전을 비교합니다.

```python
project.diff_prompt("intent_classifier", "0.1.0", "0.2.0")
# {
#     "id": "intent_classifier",
#     "from_version": "0.1.0",
#     "to_version": "0.2.0",
#     "changed": True,
#     "prompt_length_delta": 42,
#     "lines_added": 5,
#     "lines_removed": 2,
#     "model_config_changed": True,
#     "checksum_from": "sha256...",
#     "checksum_to": "sha256...",
#     "unified_diff": "--- 0.1.0\n+++ 0.2.0\n@@ -1,3 +1,5 @@\n..."
# }
```

---

## 스냅샷 관리

스냅샷은 deploy된 프롬프트의 파일을 복사하여 독립적으로 저장합니다.
프롬프트가 삭제되어도 기존 스냅샷은 영향 없습니다.

### `create_snapshot(bump_level="patch") -> dict`

현재 프로덕션에 배포된 모든 프롬프트를 스냅샷으로 캡처합니다.
deploy 안 된 프롬프트는 제외됩니다.
`snapshot_checksum`으로 동일한 프로덕션 상태를 식별할 수 있습니다.

```python
project.create_snapshot()
project.create_snapshot(bump_level="minor")
project.create_snapshot(bump_level="major")
# {
#     "version": "0.1.0",
#     "created_at": "2026-04-03T10:30:00Z",
#     "snapshot_checksum": "sha256...",
#     "prompt_count": 2,
#     "prompts": {
#         "intent_classifier": {
#             "version": "0.2.0",
#             "prompt_checksum": "sha256...",
#             "model_config_checksum": "sha256..."
#         },
#         "summarizer": {
#             "version": "0.1.0",
#             "prompt_checksum": "sha256...",
#             "model_config_checksum": "sha256..."
#         }
#     }
# }
```

### `list_snapshots() -> list[str]`

스냅샷 버전 목록을 semver 순으로 반환합니다.

```python
project.list_snapshots()
# ["0.1.0", "0.1.1", "0.2.0"]
```

### `get_snapshot(version) -> dict`

스냅샷 매니페스트를 반환합니다. `create_snapshot`과 동일한 형태입니다.

```python
project.get_snapshot("0.1.0")
```

### `read_snapshot(version) -> dict`

스냅샷 내부의 복사된 파일에서 각 프롬프트의 실제 내용을 포함하여 반환합니다.

```python
project.read_snapshot("0.1.0")
# {
#     "version": "0.1.0",
#     "created_at": "2026-04-03T10:30:00Z",
#     "prompt_count": 2,
#     "prompts": {
#         "intent_classifier": {
#             "version": "0.2.0",
#             "llm": {
#                 "provider": "openai",
#                 "model": "gpt-4.1",
#                 "params": {"temperature": 0.2, "max_tokens": 300}
#             },
#             "prompt": "Classify the intent of the user input.",
#             "metadata": {
#                 "id": "intent_classifier",
#                 "version": "0.2.0",
#                 "description": "...",
#                 "author": "...",
#                 "created_at": "...",
#                 "source_file": "...",
#                 "prompt_checksum": "sha256...",
#                 "model_config_checksum": "sha256...",
#                 "template_checksum": "sha256..."
#             }
#         },
#         "summarizer": { ... }
#     }
# }

# 특정 프롬프트만 접근
snapshot = project.read_snapshot("0.1.0")
snapshot["prompts"]["intent_classifier"]
```

### `export_snapshot(version, output_path=None) -> dict`

스냅샷을 zip 파일로 내보냅니다.
`output_path`가 None이면 프로젝트 루트에 `snapshot-{version}.zip`으로 저장됩니다.

```python
# 기본 경로
project.export_snapshot("0.1.0")
# {"version": "0.1.0", "output_path": "/path/to/project/snapshot-0.1.0.zip"}

# 경로 지정
project.export_snapshot("0.1.0", output_path="./exports/my_snapshot.zip")
# {"version": "0.1.0", "output_path": "/path/to/exports/my_snapshot.zip"}
```

zip 내부 구조:
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

### `diff_snapshot(from_version, to_version) -> dict`

두 스냅샷을 비교하여 프롬프트의 추가/제거/변경을 분류합니다.

```python
project.diff_snapshot("0.1.0", "0.2.0")
# {
#     "from_version": "0.1.0",
#     "to_version": "0.2.0",
#     "added_ids": ["translator"],
#     "removed_ids": ["summarizer"],
#     "changed_ids": [
#         {"id": "intent_classifier", "from_version": "0.2.0", "to_version": "0.3.0"}
#     ]
# }
```

---

## 히스토리

프롬프트와 스냅샷 각각 `history.jsonl`에 이벤트가 append-only로 기록됩니다.

**프롬프트 이벤트:**
```json
{"ts": "...", "event": "add", "id": "intent_classifier", "version": "0.1.0", "template_checksum": "sha256..."}
{"ts": "...", "event": "deploy", "id": "intent_classifier", "from_version": "0.1.0", "to_version": "0.2.0"}
{"ts": "...", "event": "rollback", "id": "intent_classifier", "from_version": "0.2.0", "to_version": "0.1.0"}
```

**스냅샷 이벤트:**
```json
{"ts": "...", "event": "create", "version": "0.1.0", "prompt_count": 3}
```

---

## .pvm 디렉토리 구조

```
.pvm/
├── config.yaml                          # 프로젝트 메타데이터
├── settings/
│   └── template.yaml                    # 기본 프롬프트 템플릿
├── prompts/
│   └── <prompt_id>/
│       ├── info.yaml                    # 최초 생성시 고정 메타데이터
│       ├── production.json              # 프로덕션 포인터 (version, previous_versions)
│       ├── history.jsonl                # 이벤트 이력 (add, deploy, rollback)
│       └── versions/
│           └── <semver>/
│               ├── prompt.md            # 프롬프트 텍스트
│               ├── model_config.json    # LLM 설정
│               ├── template.yaml        # 원본 YAML 템플릿 사본
│               └── metadata.json        # 체크섬, 작성자, 타임스탬프
└── snapshots/
    ├── history.jsonl                    # 스냅샷 이벤트 이력 (create)
    └── versions/
        └── <semver>/
            ├── manifest.json            # 매니페스트 (snapshot_checksum, 프롬프트 목록)
            └── prompts/
                └── <prompt_id>/
                    ├── prompt.md
                    ├── model_config.json
                    └── metadata.json
```

---

## 예외

모든 예외는 `PVMError`를 상속합니다.

| 예외 | 발생 조건 |
|------|-----------|
| `NotValidProjectError` | `.pvm/` 레이아웃이 유효하지 않을 때 |
| `AlreadyInitializedError` | 이미 초기화된 프로젝트에서 `init` 호출시 |
| `PromptNotFoundError` | 존재하지 않는 prompt_id 참조시 |
| `VersionNotFoundError` | 존재하지 않는 버전 참조시 |
| `InvalidPromptTemplateError` | YAML 템플릿 검증 실패시 |
| `InvalidVersionError` | semver 형식이 아닌 버전 문자열 |
