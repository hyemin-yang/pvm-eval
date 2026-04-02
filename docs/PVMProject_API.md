# PVMProject API Reference

`PVMProject`는 pvm의 모든 기능을 제공하는 파사드 클래스입니다.
CLI 없이 Python 코드에서 직접 사용할 수 있습니다.

---

## 인스턴스 생성

```python
from pathlib import Path
from pvm.project import PVMProject

# 현재 작업 디렉토리 기준
project = PVMProject.cwd()

# 특정 경로 지정
project = PVMProject(Path("/path/to/project"))
```

---

## 프로젝트 관리

### `init(name="my-project") -> dict`

`.pvm/` 디렉토리 구조를 생성하고 프로젝트를 초기화합니다.

```python
result = project.init("my-project")
# {"project_id": "01J...", "name": "my-project", "created_at": "...", "root": "..."}
```

### `is_valid() -> bool`

현재 루트에 유효한 `.pvm/` 레이아웃이 존재하는지 확인합니다.

### `require_valid() -> None`

유효하지 않은 프로젝트이면 `NotValidProjectError`를 발생시킵니다.
`init`을 제외한 모든 메서드에서 내부적으로 호출됩니다.

### `load_config() -> dict`

`.pvm/config.yaml`을 읽어 프로젝트 메타데이터를 반환합니다.

```python
config = project.load_config()
# {"project_id": "...", "name": "my-project", "created_at": "..."}
```

### `load_template() -> dict`

`.pvm/settings/template.yaml`의 기본 프롬프트 템플릿을 반환합니다.

---

## 프롬프트 관리

### `add_prompt(template_path, bump_level="patch") -> dict`

YAML 템플릿 파일을 읽어 새로운 불변 버전을 생성합니다.

- `template_path`: YAML 템플릿 파일 경로 (`str | Path`)
- `bump_level`: `"patch"` | `"minor"` | `"major"`

```python
result = project.add_prompt("prompt.yaml", bump_level="patch")
# 변경 있을 때: {"id": "intent_classifier", "version": "0.1.0", "changed": True}
# 중복일 때:   {"id": "intent_classifier", "changed": False, "reason": "no_changes"}
```

**동작:**
1. 템플릿의 `id`, `llm`, `prompt` 필드 검증
2. SHA-256 체크섬으로 최신 버전과 비교하여 중복이면 no-op
3. 버전 디렉토리에 4개 파일 저장 (`prompt.md`, `model_config.json`, `template.yaml`, `metadata.json`)
4. `history.jsonl`에 `add` 이벤트 기록

### `deploy(prompt_id, version=None) -> dict`

특정 버전을 프로덕션으로 배포합니다. `version`이 None이면 최신 버전을 자동 선택합니다.

```python
result = project.deploy("intent_classifier", "0.2.0")
# 성공:       {"id": "intent_classifier", "version": "0.2.0", "changed": True, "from_version": "0.1.0"}
# 이미 배포:  {"id": "intent_classifier", "version": "0.2.0", "changed": False, "reason": "already_deployed"}
# 버전 없음:  {"id": "intent_classifier", "version": "0.9.0", "changed": False, "reason": "version_not_found"}
```

**동작:**
1. 현재 프로덕션 버전을 `production.json`의 `previous_versions` 스택에 push
2. `production.json`의 `version`을 대상 버전으로 갱신
3. `history.jsonl`에 `deploy` 이벤트 기록

### `rollback(prompt_id) -> dict`

프로덕션을 이전 배포 버전으로 롤백합니다.

```python
result = project.rollback("intent_classifier")
# 성공:       {"id": "intent_classifier", "changed": True, "from_version": "0.2.0", "to_version": "0.1.0"}
# 대상 없음:  {"id": "intent_classifier", "changed": False, "reason": "no_rollback_target"}
# 미배포:     {"id": "intent_classifier", "changed": False, "reason": "no_production_version"}
```

**동작:**
1. `production.json`의 `previous_versions` 스택에서 pop
2. 스택이 비어있으면 `no_rollback_target` 반환
3. `history.jsonl`에 `rollback` 이벤트 기록 (append-only, 삭제 없음)

### `get_prompt(prompt_id, version=None) -> dict`

프롬프트 내용을 조회합니다. 버전 결정 우선순위: 명시적 version → 프로덕션 버전 → 최신 버전

```python
result = project.get_prompt("intent_classifier")
# {"id": "...", "version": "0.2.0", "llm": {...}, "prompt": "...", "metadata": {...}}
```

### `get_prompt_info(prompt_id) -> dict`

프롬프트의 메타데이터와 버전 요약 정보를 반환합니다.

```python
result = project.get_prompt_info("intent_classifier")
# {
#   "id": "intent_classifier",
#   "info": {...},                  # info.yaml (최초 생성시 고정)
#   "versions": ["0.1.0", "0.2.0"],
#   "latest_version": "0.2.0",
#   "production": {"id": "...", "version": "0.1.0", "updated_at": "..."} or None
# }
```

### `list_prompt_ids() -> list[str]`

프로젝트 내 모든 프롬프트 ID를 정렬하여 반환합니다.

```python
ids = project.list_prompt_ids()
# ["intent_classifier", "summarizer"]
```

### `list_prompt_versions(prompt_id) -> list[str]`

특정 프롬프트의 모든 버전을 semver 순으로 반환합니다.

```python
versions = project.list_prompt_versions("intent_classifier")
# ["0.1.0", "0.1.1", "0.2.0"]
```

### `diff_prompt(prompt_id, from_version, to_version) -> dict`

두 프롬프트 버전을 비교합니다.

```python
result = project.diff_prompt("intent_classifier", "0.1.0", "0.2.0")
# {
#   "id": "intent_classifier",
#   "from_version": "0.1.0",
#   "to_version": "0.2.0",
#   "changed": True,
#   "prompt_length_delta": 42,
#   "lines_added": 5,
#   "lines_removed": 2,
#   "model_config_changed": False,
#   "checksum_from": "sha256...",
#   "checksum_to": "sha256...",
#   "unified_diff": "--- ...\n+++ ..."
# }
```

---

## 스냅샷 관리

### `create_snapshot(bump_level="patch") -> dict`

현재 프로덕션에 배포된 모든 프롬프트를 하나의 스냅샷으로 캡처합니다.
프로덕션 버전이 없는 프롬프트는 제외됩니다.

```python
result = project.create_snapshot(bump_level="patch")
# {"version": "0.1.0", "created_at": "...", "prompt_count": 3, "prompts": {...}}
```

### `list_snapshots() -> list[str]`

스냅샷 버전 목록을 semver 순으로 반환합니다.

```python
versions = project.list_snapshots()
# ["0.1.0", "0.1.1"]
```

### `get_snapshot(version) -> dict`

스냅샷 매니페스트를 반환합니다. 버전 번호와 체크섬만 포함된 참조 정보입니다.

```python
result = project.get_snapshot("0.1.0")
# {"version": "0.1.0", "created_at": "...", "prompt_count": 2, "prompts": {...}}
```

### `read_snapshot(version) -> dict`

스냅샷의 참조를 역참조하여 각 프롬프트의 실제 내용(llm, prompt, metadata)을 포함한 확장 결과를 반환합니다.

```python
result = project.read_snapshot("0.1.0")
```

### `diff_snapshot(from_version, to_version) -> dict`

두 스냅샷을 비교하여 추가/제거/버전 변경된 프롬프트를 분류합니다.

```python
result = project.diff_snapshot("0.1.0", "0.2.0")
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
