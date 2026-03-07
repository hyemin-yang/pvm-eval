# PVM MVP Implementation Status

이 문서는 `DESIGN.md` 기준 MVP 구현 결과를 현재 코드 상태로 요약한 것이다.

## 현재 상태

- MVP 구현 완료
- 패키지 레이아웃은 루트 `pvm/`
- CLI는 `Typer` 기반
- 테스트는 `pytest` 기반

## 구현 완료 범위

### 1. 패키지 골격

완료:

- [x] `pvm/__init__.py`
- [x] `pvm/project.py`
- [x] `pvm/core/errors.py`
- [x] `pvm/core/paths.py`
- [x] `pvm/config/`
- [x] `pvm/prompts/`
- [x] `pvm/snapshots/`
- [x] `pvm/storage/`

결과:

- `from pvm.project import PVMProject` 사용 가능
- 경로 계산과 예외 타입이 모듈화됨

### 2. 프로젝트 초기화

완료:

- [x] `.pvm/` 프로젝트 초기화
- [x] `project_id` ULID 생성
- [x] `config.yaml` 생성
- [x] `settings/template.yaml` 생성
- [x] `prompts/` 생성
- [x] `snapshots/versions/` 생성
- [x] `snapshots/history.jsonl` 생성
- [x] 최소 필수 구조 유효성 검사

현재 동작:

- `pvm init [name]`
- 이름 생략 시 `my-project`

### 3. 저장 유틸

완료:

- [x] JSON load/save
- [x] YAML load/save
- [x] checksum 유틸
- [x] JSONL history append
- [x] semver patch/minor/major bump
- [x] UTC timestamp 유틸
- [x] ULID 생성 유틸

### 4. Prompt 추가

완료:

- [x] YAML 템플릿 로드 및 검증
- [x] `id` 유효성 검사
- [x] prompt 아티팩트 저장
- [x] 중복 checksum no-op 처리
- [x] `info.yaml` 생성
- [x] `history.jsonl` append

현재 동작:

- `pvm add <file>`
- `pvm add <file> --minor`
- `pvm add <file> --major`
- 첫 버전은 항상 `0.1.0`
- 동일 내용이면 `No changes`

### 5. Prompt 조회

완료:

- [x] prompt id 목록 조회
- [x] prompt 버전 목록 조회
- [x] prompt info 조회
- [x] 특정 버전 조회
- [x] production 기준 조회
- [x] production 없을 때 latest fallback

현재 동작:

- `pvm list`
- `pvm list --id <id>`
- `pvm get <id>`
- `pvm get <id> --version <version>`
- `pvm id <id>`
- `pvm id <id> --info`
- `pvm id <id> --list`

### 6. Production 관리

완료:

- [x] deploy
- [x] rollback
- [x] append-only production history
- [x] repeated deploy no-op 처리

현재 동작:

- `pvm deploy <id>`
- `pvm deploy <id> <version>`
- `pvm rollback <id>`

규칙:

- `deploy`에서 version 생략 시 latest deploy
- 현재 production과 동일한 version deploy는 no-op
- rollback 대상이 없으면 `No rollback target`

### 7. Diff

완료:

- [x] prompt unified diff
- [x] prompt diff 요약 정보
- [x] snapshot diff

현재 동작:

- `pvm diff <id> <from_version> <to_version>`
- `pvm snapshot diff <from_version> <to_version>`

### 8. Snapshot

완료:

- [x] snapshot create
- [x] snapshot list
- [x] snapshot get
- [x] snapshot read
- [x] snapshot history append

현재 동작:

- `pvm snapshot create`
- `pvm snapshot create --minor`
- `pvm snapshot create --major`
- `pvm snapshot list`
- `pvm snapshot get <version>`
- `pvm snapshot read <version>`

규칙:

- 기본 bump는 patch
- 첫 snapshot version은 항상 `0.1.0`

### 9. CLI

완료:

- [x] Typer 기반 CLI 엔트리포인트
- [x] JSON 출력 유틸
- [x] project summary 출력
- [x] traceback 없는 예상 가능 에러 처리

현재 명령:

- [x] `pvm init [name]`
- [x] `pvm add <file> [--minor|--major]`
- [x] `pvm deploy <id> [version]`
- [x] `pvm rollback <id>`
- [x] `pvm get <id> [--version <version>]`
- [x] `pvm diff <id> <from_version> <to_version>`
- [x] `pvm list [--id <id>]`
- [x] `pvm id <id> [--info] [--list]`
- [x] `pvm log [--id <id>]`
- [x] `pvm project`
- [x] `pvm template`
- [x] `pvm snapshot create [--minor|--major]`
- [x] `pvm snapshot list`
- [x] `pvm snapshot get <version>`
- [x] `pvm snapshot read <version>`
- [x] `pvm snapshot diff <from_version> <to_version>`

### 10. 테스트

완료:

- [x] init 테스트
- [x] invalid project 테스트
- [x] add 첫 버전 생성 테스트
- [x] add patch/minor/major 테스트
- [x] add 동일 내용 no-op 테스트
- [x] deploy 테스트
- [x] repeated deploy no-op 테스트
- [x] rollback 테스트
- [x] get latest fallback 테스트
- [x] prompt diff 테스트
- [x] snapshot create/get/read/diff 테스트
- [x] CLI 스모크 테스트
- [x] CLI 예상 가능 에러 메시지 테스트

실행:

```bash
poetry run python -m pytest -q
```

## 브랜치 구현 이력

완료된 구현 흐름:

- `feat/bootstrap`
- `feat/prompt-core`
- `feat/snapshot-diff`
- `feat/cli-and-tests`

후속 개선 브랜치:

- 설치/README 정리
- flat package layout 전환
- CLI 에러 메시지 정리
- `project` 명령 개선
- semver bump 옵션 추가

## 현재 문서 기준 참고

- 설계: `DESIGN.md`
- CLI 사용법: `CLI.md`
- 사용자 개요: `README.md`
