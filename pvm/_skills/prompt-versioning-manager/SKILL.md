---
name: prompt-versioning-manager
description: >
  PVM으로 프롬프트를 관리합니다.
  TRIGGER when: 사용자가 pvm yaml 파일 생성, 프롬프트 버전 추가/등록,
  배포(deploy), 롤백(rollback), 스냅샷(snapshot) 등을 요청할 때.
  또는 "pvm", "버전 추가", "프롬프트 등록", "pvm yaml 템플릿 만들어줘" 등의
  키워드가 포함된 경우.
  DO NOT TRIGGER when: pvm과 무관한 일반 파일 변환이나 yaml 작업 요청인 경우.
---

# Prompt Versioning Manager

사용자의 요청을 파악한 뒤, 아래 흐름에 따라 단계적으로 작업을 수행한다.

모든 `pvm` 명령은 **프로젝트 루트** (`.pvm/` 디렉토리가 있는 디렉토리)에서 실행한다.

---

## 1. 전제조건 체크 (모든 작업 전 필수)

```bash
pvm project
```

- **성공** (프로젝트 정보 출력) → 계속 진행
- **실패** (`.pvm/` 없음 또는 오류) → 미초기화로 판단
  - 사용자에게 `pvm init` 수행 여부를 확인하고 동의 시 실행:
    ```bash
    pvm init [name]
    ```
  - 초기화 완료 후 작업 재개

---

## 2. 프롬프트 추가

**사용자 요청 예시**: "프롬프트 추가해줘", "새 버전 등록해줘", "이 txt 파일로 pvm yaml 만들어줘"

### 2-A. txt / md 파일 → yaml 변환 후 추가

사용자가 `.txt` 또는 `.md` 파일을 기준으로 yaml 파일 생성을 요청한 경우:

1. 전제조건 체크 수행
2. 원본 파일 내용을 읽어 프롬프트 목적과 구조를 파악한다
3. 아래 규칙으로 yaml 파일을 생성한다:
   - **파일명**: 원본 파일명에서 확장자만 교체 (`prompt.txt` → `prompt.yaml`, `my_agent.md` → `my_agent.yaml`)
   - **`id`**: 사용자가 명시하지 않은 경우, 프롬프트의 목적·역할을 분석해 snake_case로 추론 (예: 아기상어 난파선 미션 → `baby_shark_mission`)
   - **`llm.provider` / `llm.model`**: 사용자가 명시하지 않은 경우 placeholder로 남기고 안내
     ```yaml
     llm:
       provider: # 예: openai, anthropic
       model:    # 예: gpt-5.4, claude-sonnet-4-6
     ```
   - **`prompt`**: 원본 파일 내용을 그대로 사용
   - **`input_variables`**: 프롬프트 내 `{{변수명}}` 패턴을 스캔해 자동 추출; 없으면 생략
4. `llm` 필드가 placeholder 상태면 실행 전 사용자에게 먼저 채워달라고 요청
5. yaml 파일 준비 완료 후 `pvm add` 실행:
   ```bash
   pvm add <yaml_path>          # patch bump (기본값)
   pvm add <yaml_path> --minor  # minor bump
   pvm add <yaml_path> --major  # major bump
   ```
   - bump 수준은 사용자가 명시하지 않으면 인자 없이 실행 (patch)
   - 첫 추가 시 버전은 항상 `0.1.0`

### 2-B. yaml 파일이 이미 있는 경우

1. 전제조건 체크 수행
2. yaml 파일 경로 확인
   - 없으면: `pvm template`으로 템플릿 구조를 출력하고 파일 경로를 요청
   - 있으면: 해당 yaml에 `id`, `llm`, `prompt` 필드가 모두 있는지 확인
     - 누락 시: `pvm template`으로 올바른 구조를 제시하고 수정 요청
     - `llm` 필드가 빈 dict이거나 없는 경우도 유효하지 않음
3. bump 수준 확인 (기본값: patch)
4. 실행:
   ```bash
   pvm add <yaml_path> [--minor|--major]
   ```

---

## 3. 프롬프트 조회 및 탐색

**사용자 요청 예시**: "프롬프트 보여줘", "어떤 버전들이 있어?", "현재 프로덕션 버전은?"

1. 전제조건 체크 수행
2. `prompt_id`가 불명확하면 전체 목록 먼저 조회:
   ```bash
   pvm list
   ```
3. 특정 프롬프트의 요약 정보 (production 버전, 전체 버전 목록 등):
   ```bash
   pvm id <id> --info
   ```
4. 특정 버전 내용 조회:
   ```bash
   pvm get <id>                     # production 버전 → 없으면 latest
   pvm get <id> --version <version> # 특정 버전 (없으면 오류)
   ```
5. 전체 버전 이력:
   ```bash
   pvm id <id> --list
   ```

---

## 4. 버전 비교

**사용자 요청 예시**: "v1이랑 v2 비교해줘", "어떻게 바뀌었어?"

1. 전제조건 체크 수행
2. `prompt_id`, `from_version`, `to_version` 모두 필요
   - 버전이 불명확하면 `pvm id <id> --list`로 목록 조회 후 선택 유도
3. 실행:
   ```bash
   pvm diff <id> <from_version> <to_version>
   ```

---

## 5. 배포

**사용자 요청 예시**: "프로덕션에 배포해줘", "최신 버전 올려줘"

1. 전제조건 체크 수행
2. `prompt_id` 확인 → 불명확하면 `pvm list` 조회
3. `version` 확인
   - 생략 가능 (생략 시 latest 버전 배포)
   - 특정 버전 지정 시 `pvm id <id> --list`로 존재 여부 확인
4. 배포 전 현재 production 버전 확인:
   ```bash
   pvm id <id> --info
   ```
5. 실행:
   ```bash
   pvm deploy <id>            # latest 배포
   pvm deploy <id> <version>  # 특정 버전 배포
   ```
   - 현재 production과 동일한 버전이면 no-op

---

## 6. 롤백

**사용자 요청 예시**: "이전 버전으로 되돌려줘", "롤백해줘"

1. 전제조건 체크 수행
2. `prompt_id` 확인 → 불명확하면 `pvm list` 조회
3. 현재 production 버전과 이전 버전 확인:
   ```bash
   pvm id <id> --info
   ```
4. 롤백 대상을 사용자가 확인하면:
   ```bash
   pvm rollback <id>
   ```

---

## 7. 스냅샷 관리

### 스냅샷 생성

**사용자 요청 예시**: "스냅샷 찍어줘", "현재 상태 저장해줘"

1. 전제조건 체크 수행
2. production 배포된 프롬프트가 있는지 확인:
   ```bash
   pvm project
   ```
   - 배포된 프롬프트가 없으면 경고 후 사용자에게 진행 여부 확인
3. bump 수준 확인 (기본값: patch)
4. 실행:
   ```bash
   pvm snapshot create           # patch bump
   pvm snapshot create --minor   # minor bump
   pvm snapshot create --major   # major bump
   ```
   - 첫 스냅샷 버전은 항상 `0.1.0`

### 스냅샷 조회

```bash
pvm snapshot list                         # 버전 목록
pvm snapshot get <version>                # 특정 스냅샷 manifest
pvm snapshot read <version>               # 프롬프트 내용까지 포함한 전체 조회
```

### 스냅샷 비교

1. `from_version`, `to_version` 확인 → 불명확하면 `pvm snapshot list` 조회
2. 실행:
   ```bash
   pvm snapshot diff <from_version> <to_version>
   ```

---

## 8. 파괴적 작업 (직접 실행 불가)

아래 작업은 되돌릴 수 없으므로 사용자에게 위험성을 명시하고 CLI 명령을 **안내만** 한다.
**Claude가 직접 실행하지 않는다.**

| 작업 | 설명 | 안내 명령 |
|---|---|---|
| 프롬프트 삭제 | 해당 ID의 모든 버전 삭제, 복구 불가 | `pvm delete <id>` |
| 프로젝트 초기화 | `.pvm/` 전체 삭제, 복구 불가 | `pvm destroy` |
| 프로젝트 리셋 | destroy 후 재초기화, 모든 데이터 소실 | `pvm reset` |

---

## 오류 공통 처리 원칙

- 명령 실행이 실패하면 오류 메시지를 그대로 사용자에게 전달한다.
- 전제조건 미충족으로 인한 실패는 어느 단계에서 막혔는지 명확히 설명한다.
- 사용자의 의도가 불명확할 때는 작업을 임의로 진행하지 않고 확인을 요청한다.
