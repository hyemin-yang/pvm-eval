# pvm

`pvm`은 로컬 프롬프트 버전 관리 도구입니다.

관리 대상:

- `id`별 prompt version
- prompt별 production 포인터
- prompt diff
- production snapshot
- Python 라이브러리 위에 올라간 Typer 기반 CLI

## 설치

### 권장: `pipx`

`git`처럼 어디서든 `pvm` 명령을 쓰고 싶다면 `pipx` 설치가 가장 자연스럽습니다.

로컬 체크아웃에서 설치:

```bash
pipx install /path/to/pvm
```

GitHub에서 설치:

```bash
pipx install "git+https://github.com/OWNER/REPO.git@main"
```

변경 반영 후 재설치:

```bash
pipx reinstall pvm
```

버전이 올라간 릴리스를 사용한다면 다음도 가능합니다.

```bash
pipx upgrade pvm
```

### Poetry 기반 로컬 개발

```bash
poetry install -E dev
poetry run pvm --help
```

### 배포 패키지 빌드

```bash
poetry build
```

생성 결과:

- `dist/pvm-0.1.1-py3-none-any.whl`
- `dist/pvm-0.1.1.tar.gz`

wheel 설치:

```bash
pipx install dist/pvm-0.1.1-py3-none-any.whl
```

## 빠른 시작

현재 디렉토리를 프로젝트로 초기화합니다. `name`을 생략하면 `my-project`가 사용됩니다.

```bash
pvm init
```

기본 prompt 템플릿 출력:

```bash
pvm template
```

YAML 파일을 prompt version으로 추가:

```bash
pvm add prompt.yaml
```

minor/major bump:

```bash
pvm add prompt.yaml --minor
pvm add prompt.yaml --major
```

최신 버전 deploy:

```bash
pvm deploy intent_classifier
```

특정 버전 deploy:

```bash
pvm deploy intent_classifier 0.1.0
```

prompt 조회:

```bash
pvm get intent_classifier
pvm get intent_classifier --version 0.1.0
```

snapshot 생성:

```bash
pvm snapshot create
pvm snapshot create --minor
pvm snapshot create --major
```

프로젝트 요약 조회:

```bash
pvm project
```

## Prompt 템플릿

기본 YAML 템플릿은 다음과 같습니다.

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

필수 필드:

- `id`
- `llm`
- `prompt`

규칙:

- `id`는 안정적인 prompt 식별자입니다
- `id`에는 공백과 `/`를 넣을 수 없습니다
- 첫 버전은 항상 `0.1.0`입니다
- 동일한 내용이면 no-op 처리됩니다

## 프로젝트 구조

`pvm init` 이후 생성되는 `.pvm/` 구조:

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
        {version}/
          prompt.md
          model_config.json
          metadata.json
          template.yaml
  snapshots/
    history.jsonl
    versions/
      {version}.json
```

## 현재 명령어

상위 명령:

- `pvm init [name]`
- `pvm add <file> [--minor|--major]`
- `pvm deploy <id> [version]`
- `pvm rollback <id>`
- `pvm get <id> [--version <version>]`
- `pvm diff <id> <from_version> <to_version>`
- `pvm list [--id <id>]`
- `pvm id <id> [--info] [--list]`
- `pvm log [--id <id>]`
- `pvm project`
- `pvm template`

snapshot 명령:

- `pvm snapshot create [--minor|--major]`
- `pvm snapshot list`
- `pvm snapshot get <version>`
- `pvm snapshot read <version>`
- `pvm snapshot diff <from_version> <to_version>`

상세 CLI 예시는 `CLI_KO.md`를 보면 됩니다.

## 동작 규칙

- `pvm init`의 기본 프로젝트 이름은 `my-project`
- `pvm add`의 기본 bump는 patch이며 `--minor`, `--major`는 동시에 못 씀
- 첫 prompt version은 항상 `0.1.0`
- `pvm deploy <id>`는 버전을 생략하면 최신 버전을 deploy
- 현재 production과 같은 버전을 다시 deploy하면 no-op
- `pvm get <id>`는 production이 있으면 production, 없으면 latest를 반환
- `pvm get <id> --version <version>`은 strict하게 동작하며 없으면 에러
- 첫 snapshot version은 항상 `0.1.0`
- `pvm project`는 프로젝트, prompt id, version, production 마커, snapshot 목록을 함께 보여줌

## 테스트

Poetry 환경에서 테스트 실행:

```bash
poetry run python -m pytest -q
```
