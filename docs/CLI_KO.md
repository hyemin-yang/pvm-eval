# CLI 사용법

## 개요

`pvm`은 프로젝트 로컬 CLI입니다.

대부분의 명령은 이미 `.pvm/`가 존재하는 디렉토리에서 실행해야 합니다.

## 초기화

프로젝트 생성:

```bash
pvm init
```

이름을 지정해서 생성:

```bash
pvm init my-project
```

기본 YAML 템플릿 출력:

```bash
pvm template
```

바로 템플릿 파일로 만들려면:

```bash
pvm template > prompt.yaml
```

기본 출력 형태는 다음과 같습니다.

```yaml
id: "intent_classifier"
description: "Classify the user's intent"
author: "alice"

llm:
  provider: "openai"
  model: "gpt-4.1"
  params:
    temperature: 0.2
    max_tokens: 300

prompt: |
  Classify the user's intent.

input_variables:
  - user_input
  - history
```

## Prompt 명령

### `pvm add`

YAML 템플릿을 새 immutable version으로 추가합니다.

```bash
pvm add prompt.yaml
```

minor/major bump:

```bash
pvm add prompt.yaml --minor
pvm add prompt.yaml --major
```

규칙:

- 기본 bump는 patch
- `--minor`와 `--major`는 동시에 사용할 수 없음
- 첫 버전은 항상 `0.1.0`
- 동일한 내용이면 `No changes`

### `pvm list`

prompt id 목록 조회:

```bash
pvm list
```

특정 prompt의 버전 목록 조회:

```bash
pvm list --id intent_classifier
```

### `pvm get`

prompt 조회:

```bash
pvm get intent_classifier
```

특정 버전 조회:

```bash
pvm get intent_classifier --version 0.1.0
```

해결 규칙:

- `--version`이 있으면 해당 버전을 반환하거나 에러
- `--version`이 없고 production이 있으면 production 반환
- `--version`이 없고 production이 없으면 latest 반환

### `pvm deploy`

최신 버전 deploy:

```bash
pvm deploy intent_classifier
```

특정 버전 deploy:

```bash
pvm deploy intent_classifier 0.1.1
```

동작:

- `version` 생략 시 latest version 사용
- 없는 버전이면 `Version not found`
- 이미 production인 버전을 다시 deploy하면 `Already deployed to production`

### `pvm rollback`

이전 production 버전으로 rollback:

```bash
pvm rollback intent_classifier
```

대상이 없으면 `No rollback target`을 출력합니다.

### `pvm diff`

두 prompt version 비교:

```bash
pvm diff intent_classifier 0.1.0 0.1.1
```

JSON 출력에는 다음이 포함됩니다.

- `changed`
- `prompt_length_delta`
- `lines_added`
- `lines_removed`
- `model_config_changed`
- `checksum_from`
- `checksum_to`
- `unified_diff`

실제 본문 변경은 `unified_diff`를 보면 됩니다.

## 프로젝트 요약

현재 프로젝트 요약 출력:

```bash
pvm project
```

예시:

```text
project: demo-project
├── id: intent_classifier
│   ├── version: 0.1.0
│   └── version: 0.1.1 <--- production
└── snapshot: 0.1.0
```

## 메타데이터와 로그

특정 prompt id 조회:

```bash
pvm id intent_classifier
pvm id intent_classifier --info
pvm id intent_classifier --list
```

로그 조회:

```bash
pvm log
pvm log --id intent_classifier
```

## Snapshot 명령

### `pvm snapshot create`

production 상태를 snapshot으로 저장:

```bash
pvm snapshot create
```

minor/major bump:

```bash
pvm snapshot create --minor
pvm snapshot create --major
```

규칙:

- 기본 bump는 patch
- `--minor`와 `--major`는 동시에 사용할 수 없음
- 첫 snapshot version은 항상 `0.1.0`

### `pvm snapshot list`

```bash
pvm snapshot list
```

### `pvm snapshot get`

저장된 snapshot manifest 조회:

```bash
pvm snapshot get 0.1.0
```

### `pvm snapshot read`

snapshot이 가리키는 실제 prompt 내용까지 펼쳐서 조회:

```bash
pvm snapshot read 0.1.0
```

### `pvm snapshot diff`

두 snapshot 비교:

```bash
pvm snapshot diff 0.1.1 0.1.2
```

JSON 출력에는 다음이 포함됩니다.

- `added_ids`
- `removed_ids`
- `changed_ids`

`changed_ids`는 두 snapshot 사이에서 production version 매핑이 바뀐 prompt id 목록입니다.

## 에러

예상 가능한 CLI 에러는 Python traceback 없이 출력됩니다.

예시:

- invalid project directory
- missing explicit prompt version
- `0.1.0-alpha` 같은 invalid semantic version 입력
- mutually exclusive bump options

## 도움말

```bash
pvm --help
pvm snapshot --help
```
