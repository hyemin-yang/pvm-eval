# PVM MVP Implementation TODO

이 문서는 [`DESIGN.md`](/home/wjdgh/pvm/pvm/DESIGN.md)를 구현 순서 기준으로 바로 실행 가능한 TODO로 풀어쓴 것이다.

## 원칙

- 먼저 Python 라이브러리 구현
- CLI는 마지막 단계에서 얇게 래핑
- 각 단계는 파일 시스템 결과와 테스트 가능성을 기준으로 완료 처리
- MVP 범위 밖 기능은 TODO에 넣지 않음

## 1. 패키지 골격 구성

목표:

- `src/pvm/` 기본 패키지 구조 생성
- 외부 진입점 `PVMProject` 정의
- 공통 예외와 경로 유틸 준비

만들 것:

- `src/pvm/__init__.py`
- `src/pvm/project.py`
- `src/pvm/core/errors.py`
- `src/pvm/core/paths.py`
- `src/pvm/core/types.py`
- `src/pvm/config/__init__.py`
- `src/pvm/prompts/__init__.py`
- `src/pvm/snapshots/__init__.py`
- `src/pvm/storage/__init__.py`

TODO:

- [ ] `src/pvm/` 패키지 디렉토리 생성
- [ ] `PVMProject` 클래스 골격 생성
- [ ] `PVMProject.cwd()` 진입점 추가
- [ ] 예외 타입 정의
- [ ] `.pvm/`, `prompts/`, `snapshots/` 경로 계산 헬퍼 추가
- [ ] 기능 모듈 import 경로 정리

완료 조건:

- `from pvm.project import PVMProject`가 동작한다
- 프로젝트 경로 계산 로직이 한 곳에 모여 있다

## 2. 프로젝트 초기화 구현

목표:

- `.pvm/` 프로젝트 초기화 가능
- `project_id`, `name`, `created_at`를 포함한 `config.yaml` 생성
- 기본 디렉토리와 템플릿 파일 생성

만들 것:

- `src/pvm/config/init_project.py`
- 필요 시 `src/pvm/config/load_config.py`
- 필요 시 `src/pvm/config/load_template.py`

TODO:

- [ ] 유효한 프로젝트 여부 검사 함수 추가
- [ ] `.pvm/`가 이미 있으면 초기화 방어 처리
- [ ] `project_id` ULID 생성 유틸 연결
- [ ] `.pvm/config.yaml` 생성
- [ ] `.pvm/settings/template.yaml` 생성
- [ ] `.pvm/prompts/` 생성
- [ ] `.pvm/snapshots/versions/` 생성
- [ ] `.pvm/snapshots/history.jsonl` 생성
- [ ] `PVMProject.init(name)` 구현

완료 조건:

- 빈 디렉토리에서 `init` 후 설계한 `.pvm/` 구조가 생성된다
- `config.yaml`에 `project_id`, `name`, `created_at`가 기록된다

## 3. 공통 저장 유틸 구현

목표:

- JSON/YAML/텍스트/히스토리/버전 유틸 완성
- 이후 유스케이스에서 공통 재사용 가능하도록 정리

만들 것:

- `src/pvm/storage/json_io.py`
- `src/pvm/storage/yaml_io.py`
- `src/pvm/storage/checksum.py`
- `src/pvm/storage/history.py`
- `src/pvm/storage/semver.py`
- 필요 시 timestamp 유틸 파일

TODO:

- [ ] JSON load/save 함수 구현
- [ ] YAML load/save 함수 구현
- [ ] UTF-8 고정 텍스트 저장 정책 반영
- [ ] dict/list 정규화 checksum 함수 구현
- [ ] semver patch 증가 함수 구현
- [ ] UTC ISO 8601 timestamp 함수 구현
- [ ] JSONL append 유틸 구현

완료 조건:

- 파일 저장/로드 로직이 유스케이스 코드에서 중복되지 않는다
- checksum, semver, history append를 독립 테스트할 수 있다

## 4. Prompt 추가 기능 구현

목표:

- YAML 템플릿을 prompt version 아티팩트로 저장
- 중복 추가 시 no-op 처리
- prompt별 history 기록

만들 것:

- `src/pvm/prompts/add.py`

TODO:

- [ ] 템플릿 YAML 로드
- [ ] 필수 필드 `id`, `llm`, `prompt` 검증
- [ ] `id` 유효성 검사
- [ ] prompt 디렉토리 없으면 초기 구조 생성
- [ ] 최신 버전 조회
- [ ] 다음 patch 버전 계산
- [ ] 최신 버전과 checksum 비교
- [ ] 동일 내용이면 `changed=False` 결과 반환
- [ ] 새 버전 디렉토리 생성
- [ ] `prompt.md` 저장
- [ ] `model_config.json` 저장
- [ ] `metadata.json` 저장
- [ ] `template.yaml` 저장
- [ ] `info.yaml` 초기 생성 또는 안정 메타 갱신 규칙 반영
- [ ] `history.jsonl`에 `add` 이벤트 append
- [ ] `PVMProject.add_prompt(path)` 연결

완료 조건:

- 첫 add 시 `0.1.0` 생성
- 같은 내용 add 시 새 버전이 생기지 않는다
- 변경된 내용 add 시 patch가 증가한다

## 5. Prompt 조회 기능 구현

목표:

- id 목록, 버전 목록, info, prompt 본문 조회 가능
- production 기준 조회와 특정 버전 조회 모두 지원

만들 것:

- `src/pvm/prompts/list_ids.py`
- `src/pvm/prompts/get_info.py`
- `src/pvm/prompts/get.py`

TODO:

- [ ] prompt id 목록 조회 구현
- [ ] prompt 버전 목록 조회 구현
- [ ] `info.yaml`, `production.json`, 최신 버전 조합 조회 구현
- [ ] 특정 버전 prompt 읽기 구현
- [ ] production 버전 prompt 읽기 구현
- [ ] 반환 dict 스키마 통일
- [ ] `PVMProject` 메서드 연결

완료 조건:

- prompt id/버전 목록을 안정적으로 조회할 수 있다
- production 미지정 상태와 지정 상태를 구분해 읽을 수 있다

## 6. Production 관리 구현

목표:

- 특정 버전을 production으로 배포
- 이전 운영 버전으로 rollback
- append-only 운영 이력 유지

만들 것:

- `src/pvm/prompts/deploy.py`
- `src/pvm/prompts/rollback.py`

TODO:

- [ ] 대상 버전 존재 확인 로직 구현
- [ ] `deploy` no-op 정책 구현
- [ ] `production.json` 갱신 구현
- [ ] `deploy` history 이벤트 append 구현
- [ ] 현재 production 읽기 구현
- [ ] history 기반 rollback 후보 탐색 구현
- [ ] rollback no-op 정책 구현
- [ ] `rollback` history 이벤트 append 구현
- [ ] `PVMProject.deploy(id, version)` 연결
- [ ] `PVMProject.rollback(id)` 연결

완료 조건:

- 존재하는 버전은 production 전환 가능
- 존재하지 않는 버전은 no-op 처리
- rollback 시 history 삭제 없이 이전 production으로 복귀한다

## 7. Diff 기능 구현

목표:

- prompt 간 diff
- snapshot 간 diff

만들 것:

- `src/pvm/prompts/diff.py`
- `src/pvm/snapshots/diff.py`

TODO:

- [ ] `prompt.md` unified diff 생성 구현
- [ ] prompt 길이 변화량 계산
- [ ] 추가 줄 수 계산
- [ ] 삭제 줄 수 계산
- [ ] model config 변경 여부 비교
- [ ] checksum 전/후 반환
- [ ] snapshot manifest 비교 구현
- [ ] `added_ids`, `removed_ids`, `changed_ids` 분류
- [ ] `changed_ids`에 `from_version`, `to_version` 포함
- [ ] `PVMProject.diff_prompt(...)` 연결
- [ ] `PVMProject.diff_snapshot(...)` 연결

완료 조건:

- 두 prompt version 차이를 요약과 diff 텍스트로 반환할 수 있다
- 두 snapshot 차이를 id 단위로 분류해 반환할 수 있다

## 8. Snapshot 기능 구현

목표:

- 현재 production 상태를 snapshot으로 저장
- snapshot 목록/정의/실제 내용 조회 가능

만들 것:

- `src/pvm/snapshots/create.py`
- `src/pvm/snapshots/get.py`
- `src/pvm/snapshots/list.py`
- `src/pvm/snapshots/read.py`

TODO:

- [ ] 모든 prompt id 순회 구현
- [ ] production 설정된 id만 수집
- [ ] snapshot 다음 patch 버전 계산
- [ ] snapshot manifest 생성
- [ ] `.pvm/snapshots/versions/{version}.json` 저장
- [ ] snapshot history append
- [ ] snapshot 버전 목록 조회 구현
- [ ] snapshot manifest 조회 구현
- [ ] snapshot read 구현
- [ ] manifest 기준 실제 prompt/llm/metadata 펼치기 구현
- [ ] `PVMProject.create_snapshot()` 연결
- [ ] `PVMProject.list_snapshots()` 연결
- [ ] `PVMProject.get_snapshot(version)` 연결
- [ ] `PVMProject.read_snapshot(version)` 연결

완료 조건:

- production 상태가 snapshot 파일로 보존된다
- snapshot 정의와 실제 펼친 내용을 각각 읽을 수 있다

## 9. 테스트 작성

목표:

- 핵심 유스케이스 회귀 테스트 확보
- 파일 시스템 결과까지 검증

만들 것:

- 테스트 디렉토리 구조
- pytest 기반 테스트 파일들

TODO:

- [ ] init 테스트
- [ ] invalid project 테스트
- [ ] add 첫 버전 생성 테스트
- [ ] add patch 증가 테스트
- [ ] add 동일 내용 no-op 테스트
- [ ] deploy 테스트
- [ ] rollback 테스트
- [ ] prompt diff 테스트
- [ ] snapshot create 테스트
- [ ] snapshot get 테스트
- [ ] snapshot read 테스트
- [ ] snapshot diff 테스트
- [ ] 생성된 파일 내용 검증 추가

완료 조건:

- 핵심 라이브러리 기능에 회귀 테스트가 있다
- return 값뿐 아니라 실제 파일 구조와 내용도 검증한다

## 10. CLI 래퍼 추가

목표:

- 라이브러리 API 위에 얇은 CLI 제공
- 출력 formatting만 CLI 레이어에서 처리

만들 것:

- CLI 엔트리포인트 모듈
- 서브커맨드별 인자 파서

TODO:

- [ ] `pvm init`
- [ ] `pvm add`
- [ ] `pvm deploy`
- [ ] `pvm rollback`
- [ ] `pvm get`
- [ ] `pvm diff`
- [ ] `pvm snapshot create`
- [ ] `pvm snapshot list`
- [ ] `pvm snapshot get`
- [ ] `pvm snapshot read`
- [ ] `pvm snapshot diff`
- [ ] `pvm list`
- [ ] `pvm id`
- [ ] `pvm log`
- [ ] `pvm tree`
- [ ] no-op 메시지 처리
- [ ] 사람이 읽기 쉬운 출력 포맷 정리

완료 조건:

- CLI는 입력 파싱과 출력만 담당한다
- 실제 동작은 모두 `PVMProject` 메서드를 호출한다

## 권장 우선순위

실제 구현은 문서 순서를 그대로 따르기보다, "빨리 동작하는 세로 슬라이스를 만들고 바로 검증하는 순서"가 낫다.

### Phase 1. 기반 준비

순서:

1. 1단계 패키지 골격 구성
2. 3단계 공통 저장 유틸 구현
3. 2단계 프로젝트 초기화 구현

이유:

- 경로, 예외, 저장 유틸이 먼저 있어야 이후 유스케이스 코드가 단순해진다.
- `init`은 저장 유틸 위에서 바로 구현하는 편이 중복이 적다.

완료 기준:

- 빈 디렉토리에서 `.pvm/` 프로젝트 생성 가능
- `config.yaml`과 템플릿 파일이 정상 생성됨

### Phase 2. Prompt 기본 흐름 완성

순서:

1. 4단계 prompt add
2. 5단계 prompt 조회
3. 6단계 production 관리

이유:

- `add -> get -> deploy/rollback` 흐름이 닫혀야 prompt 도메인이 usable 상태가 된다.
- snapshot보다 먼저 prompt 라이프사이클을 안정화하는 편이 테스트와 디버깅이 쉽다.

완료 기준:

- prompt version 생성 가능
- production 조회/배포/롤백 가능

### Phase 3. 테스트 1차 고정

순서:

1. 9단계 중 init/add/get/deploy/rollback 관련 테스트 먼저 작성

이유:

- snapshot과 diff로 넘어가기 전에 prompt 코어를 고정해야 회귀가 줄어든다.
- 이 단계에서 파일 구조 검증까지 같이 묶는 것이 좋다.

완료 기준:

- core prompt 흐름에 대한 회귀 테스트 확보

### Phase 4. Snapshot 기능

순서:

1. 8단계 snapshot 기능 구현

이유:

- snapshot은 prompt production 상태가 안정된 뒤에 올리는 게 자연스럽다.
- diff보다 먼저 snapshot 실체를 만들어야 snapshot diff도 의미가 생긴다.

완료 기준:

- snapshot create/list/get/read 가능

### Phase 5. Diff 기능

순서:

1. 7단계 prompt diff
2. 7단계 snapshot diff

이유:

- diff는 이미 저장된 버전/스냅샷이 있어야 검증이 쉽다.
- snapshot 실체 없이 snapshot diff부터 만들면 테스트 세팅이 번거롭다.

완료 기준:

- prompt diff와 snapshot diff 모두 결과 dict를 안정적으로 반환

### Phase 6. 테스트 2차 고정

순서:

1. 9단계 중 diff/snapshot 관련 테스트 추가

이유:

- MVP 코어가 완성된 시점에서 전체 회귀 테스트를 마무리한다.

완료 기준:

- init/add/get/deploy/rollback/diff/snapshot 전체 테스트 확보

### Phase 7. CLI 래퍼

순서:

1. 10단계 전체

이유:

- CLI는 라이브러리 API가 고정된 뒤 붙이는 게 가장 싸다.

완료 기준:

- 주요 라이브러리 기능을 CLI로 호출 가능

## 체크포인트

- Phase 1 완료 시: 라이브러리 뼈대와 프로젝트 초기화 가능
- Phase 2 완료 시: prompt version 관리 기능 usable
- Phase 3 완료 시: prompt 코어 회귀 안정성 확보
- Phase 4~5 완료 시: snapshot과 diff를 포함한 MVP 코어 완성
- Phase 6 완료 시: 전체 라이브러리 회귀 테스트 확보
- Phase 7 완료 시: 사용자 CLI 진입점 제공
