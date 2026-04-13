# pvm

`pvm`은 로컬에서 프롬프트 버전을 관리하고, 웹 UI에서 비교/평가까지 할 수 있는 도구입니다.

## 설치

### 1. 레포 clone

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO/prompt_versioning_manager
```

### 2. `pipx`로 설치

`pvm` 명령어를 전역처럼 편하게 쓰려면 `pipx` 설치를 권장합니다.

```bash
pipx install .
```

개발 중 다시 설치할 때:

```bash
pipx reinstall pvm
```

GitHub에서 바로 설치하려면:

```bash
pipx install "git+https://github.com/OWNER/REPO.git@main#subdirectory=prompt_versioning_manager"
```

## 빠른 시작

프로젝트 작업 디렉토리로 이동한 뒤 초기화합니다.

```bash
mkdir my-prompt-project
cd my-prompt-project
pvm init
```

기본 템플릿을 보고 싶으면:

```bash
pvm template
```

예시 `prompt.yaml`

```yaml
id: intent_classifier
description: 사용자 의도를 분류하는 프롬프트
author: alice

llm:
  provider: openai
  model: gpt-4.1

prompt: |
  사용자의 입력을 보고 의도를 분류하세요.
```

프롬프트 추가:

```bash
pvm add prompt.yaml
```

배포 버전 지정:

```bash
pvm deploy intent_classifier
```

현재 프롬프트 조회:

```bash
pvm get intent_classifier
```

스냅샷 생성:

```bash
pvm snapshot create
```

## 웹 UI

프로젝트 디렉토리에서 실행:

```bash
pvm ui
```

브라우저에서 아래 주소로 접속하면 됩니다.

```text
http://127.0.0.1:8001
```

웹 UI에서는 다음 작업을 할 수 있습니다.

- 프롬프트 목록 조회
- 버전별 내용 확인
- diff 확인
- deploy / rollback
- snapshot 생성 및 비교
- Judge eval 실행

Judge eval 파이프라인은 패키지 안에 번들되어 있어서, 별도로 `judge-prompt-generation` 레포를 받을 필요가 없습니다.

## 자주 쓰는 명령어

```bash
pvm init
pvm template
pvm add prompt.yaml
pvm add prompt.yaml --minor
pvm add prompt.yaml --major
pvm list
pvm get <PROMPT_ID>
pvm deploy <PROMPT_ID>
pvm rollback <PROMPT_ID>
pvm snapshot create
pvm project
pvm ui
```

## 참고

- Python 3.11 이상이 필요합니다.
- 작업 데이터는 현재 디렉토리의 `.pvm/` 아래에 저장됩니다.
- 첫 버전은 항상 `0.1.0`부터 시작합니다.
