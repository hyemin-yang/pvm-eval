# PVM Server Design

## 개요

pvm CLI 라이브러리를 기반으로 REST API 서버와 Web UI를 구축하는 설계 문서다.

CLI를 제거하는 것이 아니라, 기존 CLI와 병행하여 웹 기반 인터페이스를 추가하는 것이 목표다.

---

## 핵심 아키텍처 결정

### 기존 라이브러리 재사용

기존 `PVMProject` 라이브러리를 **변경 없이** 재사용한다. 서버는 서비스 레이어에서 `PVMProject`를 호출하는 구조로, 검증된 비즈니스 로직을 그대로 활용한다.

```
[Web UI]
    │  HTTP
    ▼
[FastAPI]  ←→  [SQLite DB]     ← 프로젝트 레지스트리 (Phase 1)
    │
[Service Layer]                ← PVMProject 호출 조정
    │
[PVMProject (기존 라이브러리)] ← 비즈니스 로직 재사용
    │
[서버 스토리지]
  ~/.pvm-server/
    {project_id}/
      .pvm/                    ← 기존 파일 구조 그대로
```

### 스토리지 전략

- **Phase 1**: 서버가 프로젝트별 디렉토리를 관리 (`~/.pvm-server/{project_id}/.pvm/`), DB는 레지스트리 역할만 수행
- **Phase 2 이후**: DB 스토리지 레이어로 전환 (서비스 레이어만 교체)

이 방식의 이유:
- 기존 검증된 코드 즉시 재사용 가능
- 점진적 마이그레이션 가능
- 초기 개발 속도 확보

---

## 디렉토리 구조

```
pvm/                    ← 기존 라이브러리 (변경 없음)
server/
  main.py               ← FastAPI 앱 진입점
  config.py             ← 환경설정 (스토리지 경로, DB 경로 등)
  dependencies.py       ← FastAPI 의존성 (DB 세션, 서비스 인스턴스)
  │
  db/
    engine.py           ← SQLAlchemy 엔진 설정
    models.py           ← ORM 모델
    session.py          ← DB 세션 관리
  │
  routers/
    projects.py         ← /api/projects
    prompts.py          ← /api/projects/{id}/prompts
    snapshots.py        ← /api/projects/{id}/snapshots
  │
  schemas/              ← Pydantic 요청/응답 모델
    projects.py
    prompts.py
    snapshots.py
    common.py
  │
  services/             ← PVMProject 호출 조정 레이어
    project_service.py
    prompt_service.py
    snapshot_service.py
  │
  ui/
    static/
      css/
      js/
    templates/          ← Jinja2 템플릿
```

---

## 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| API 프레임워크 | FastAPI | 자동 Swagger, Pydantic 통합, 비동기 지원 |
| DB | SQLite | 로컬 호스팅, 설치 zero, 단일 파일 |
| ORM | SQLAlchemy | DB 교체 시 connection string 1줄 변경으로 충분 |
| UI | Jinja2 + HTMX | 빌드 없음, Python만으로 완결, 나중에 React 전환 가능 |
| 실행 | uvicorn | FastAPI 표준 |

---

## DB 스키마

### Phase 1: 프로젝트 레지스트리

```sql
CREATE TABLE projects (
    id           TEXT PRIMARY KEY,   -- ULID
    name         TEXT NOT NULL,
    storage_path TEXT NOT NULL,      -- 서버 내 .pvm/ 루트 경로
    created_at   TEXT NOT NULL
);
```

실제 프롬프트 데이터(`versions`, `history`, `production`)는 모두 `.pvm/` 파일에서 `PVMProject`가 읽어오므로 DB에 저장하지 않는다.

### Phase 2: 협업 기능 (추후 추가)

```sql
CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE project_members (
    project_id TEXT NOT NULL REFERENCES projects(id),
    user_id    TEXT NOT NULL REFERENCES users(id),
    role       TEXT NOT NULL,  -- viewer / editor / reviewer / deployer / admin
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE proposals (
    id          TEXT PRIMARY KEY,   -- ULID
    project_id  TEXT NOT NULL REFERENCES projects(id),
    prompt_id   TEXT NOT NULL,
    version     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
    created_by  TEXT NOT NULL REFERENCES users(id),
    reviewed_by TEXT REFERENCES users(id),
    comment     TEXT,
    created_at  TEXT NOT NULL,
    reviewed_at TEXT
);
```

---

## 서비스 레이어

기존 `PVMProject`와 API 레이어 사이의 조정 역할을 한다.

### ProjectService

```python
class ProjectService:
    def __init__(self, db: Session, storage_root: Path):
        self.db = db
        self.storage_root = storage_root

    def _get_pvm(self, project_id: str) -> PVMProject:
        row = self.db.query(ProjectModel).filter_by(id=project_id).first()
        if not row:
            raise ProjectNotFoundError(project_id)
        return PVMProject(Path(row.storage_path))

    def create(self, name: str) -> dict:
        project_id = new_ulid()
        storage_path = self.storage_root / project_id
        storage_path.mkdir(parents=True)
        pvm = PVMProject(storage_path)
        result = pvm.init(name)
        self.db.add(ProjectModel(id=project_id, name=name,
                                 storage_path=str(storage_path),
                                 created_at=now_utc()))
        self.db.commit()
        return result

    def list(self) -> list[dict]: ...
    def summary(self, project_id: str) -> dict: ...
    def delete(self, project_id: str) -> None: ...
```

### PromptService

```python
class PromptService:
    def __init__(self, project_service: ProjectService):
        self.ps = project_service

    def add(self, project_id: str, yaml_content: str, bump_level: str) -> dict:
        """YAML 문자열을 임시 파일로 쓰고 PVMProject.add_prompt 호출."""
        pvm = self.ps._get_pvm(project_id)
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False,
                                         mode="w", encoding="utf-8") as f:
            f.write(yaml_content)
            tmp = Path(f.name)
        try:
            return pvm.add_prompt(tmp, bump_level=bump_level)
        finally:
            tmp.unlink()

    def deploy(self, project_id, prompt_id, version=None) -> dict: ...
    def rollback(self, project_id, prompt_id) -> dict: ...
    def get(self, project_id, prompt_id, version=None) -> dict: ...
    def diff(self, project_id, prompt_id, from_ver, to_ver) -> dict: ...
    def list_ids(self, project_id) -> list[str]: ...
    def list_versions(self, project_id, prompt_id) -> list[str]: ...
    def get_info(self, project_id, prompt_id) -> dict: ...
    def get_log(self, project_id, prompt_id) -> str: ...
```

### SnapshotService

```python
class SnapshotService:
    def __init__(self, project_service: ProjectService):
        self.ps = project_service

    def create(self, project_id, bump_level="patch") -> dict: ...
    def list(self, project_id) -> list[str]: ...
    def get(self, project_id, version) -> dict: ...
    def read(self, project_id, version) -> dict: ...
    def diff(self, project_id, from_ver, to_ver) -> dict: ...
```

---

## API 설계

### Projects

| Method | Path | 동작 | 대응 CLI |
|--------|------|------|---------|
| GET | `/api/projects` | 프로젝트 목록 | - |
| POST | `/api/projects` | 프로젝트 생성 | `pvm init` |
| GET | `/api/projects/{pid}` | 프로젝트 요약 | `pvm project` |
| DELETE | `/api/projects/{pid}` | 프로젝트 삭제 | - |

### Prompts

| Method | Path | 동작 | 대응 CLI |
|--------|------|------|---------|
| GET | `/api/projects/{pid}/prompts` | id 목록 | `pvm list` |
| POST | `/api/projects/{pid}/prompts` | 버전 추가 | `pvm add` |
| GET | `/api/projects/{pid}/prompts/{id}` | production 조회 | `pvm get {id}` |
| GET | `/api/projects/{pid}/prompts/{id}/info` | 메타 정보 | `pvm id {id} --info` |
| GET | `/api/projects/{pid}/prompts/{id}/versions` | 버전 목록 | `pvm list --id {id}` |
| GET | `/api/projects/{pid}/prompts/{id}/versions/{version}` | 특정 버전 | `pvm get {id} --version` |
| POST | `/api/projects/{pid}/prompts/{id}/deploy` | 배포 | `pvm deploy` |
| POST | `/api/projects/{pid}/prompts/{id}/rollback` | 롤백 | `pvm rollback` |
| GET | `/api/projects/{pid}/prompts/{id}/diff` | 버전 간 diff | `pvm diff` |
| GET | `/api/projects/{pid}/prompts/{id}/log` | 히스토리 | `pvm log --id` |

### Snapshots

| Method | Path | 동작 | 대응 CLI |
|--------|------|------|---------|
| GET | `/api/projects/{pid}/snapshots` | 목록 | `pvm snapshot list` |
| POST | `/api/projects/{pid}/snapshots` | 생성 | `pvm snapshot create` |
| GET | `/api/projects/{pid}/snapshots/{version}` | manifest | `pvm snapshot get` |
| GET | `/api/projects/{pid}/snapshots/{version}/read` | 전체 내용 | `pvm snapshot read` |
| GET | `/api/projects/{pid}/snapshots/diff` | 두 스냅샷 diff | `pvm snapshot diff` |

### 요청/응답 스키마

```python
# POST /api/projects/{pid}/prompts
class AddPromptRequest(BaseModel):
    yaml_content: str           # YAML 파일 내용 (문자열)
    bump_level: str = "patch"   # patch | minor | major

# POST /api/projects/{pid}/prompts/{id}/deploy
class DeployRequest(BaseModel):
    version: str | None = None  # None이면 latest

# GET /api/projects/{pid}/prompts/{id}/diff?from=0.1.0&to=0.1.1
# Query parameter로 from, to 전달

# POST /api/projects/{pid}/snapshots
class CreateSnapshotRequest(BaseModel):
    bump_level: str = "patch"   # patch | minor | major
```

---

## 에러 처리

기존 `PVMError` 계층을 HTTP 상태코드로 매핑한다.

```python
from pvm.core.errors import (
    NotValidProjectError,
    PromptNotFoundError,
    VersionNotFoundError,
    InvalidPromptTemplateError,
    AlreadyInitializedError,
)

# main.py 에러 핸들러 등록
@app.exception_handler(PromptNotFoundError)
async def prompt_not_found(request, exc):
    return JSONResponse(status_code=404, content={"error": str(exc)})

@app.exception_handler(VersionNotFoundError)
async def version_not_found(request, exc):
    return JSONResponse(status_code=404, content={"error": str(exc)})

@app.exception_handler(InvalidPromptTemplateError)
async def invalid_template(request, exc):
    return JSONResponse(status_code=422, content={"error": str(exc)})

@app.exception_handler(AlreadyInitializedError)
async def already_initialized(request, exc):
    return JSONResponse(status_code=409, content={"error": str(exc)})
```

| PVMError | HTTP |
|----------|------|
| `PromptNotFoundError` | 404 |
| `VersionNotFoundError` | 404 |
| `InvalidPromptTemplateError` | 422 |
| `AlreadyInitializedError` | 409 |
| `NotValidProjectError` | 500 (서버 내부 오류) |

---

## UI 페이지 설계

### 페이지 목록

```
/                              대시보드
  - 프로젝트 카드 목록
  - 프로젝트 생성 버튼

/projects/{id}                 프로젝트 뷰
  - 트리 구조 (pvm project 출력 기반)
  - 프롬프트 id 목록 + production 상태
  - 스냅샷 목록

/projects/{id}/prompts/{pid}   프롬프트 뷰
  - 버전 타임라인 (세로 or 가로)
  - production 버전 하이라이트
  - 현재 버전 내용 (prompt.md, model config)
  - Deploy / Rollback 버튼

/projects/{id}/prompts/{pid}/diff
  - from / to 버전 선택기
  - unified diff 렌더링
  - model config 변경 여부 표시

/projects/{id}/snapshots       스냅샷 목록
/projects/{id}/snapshots/{version}
  - id → version 매핑 테이블
  - 이전 스냅샷과 diff 보기
```

### UI 기술 방향

**초기: Jinja2 + HTMX**
- Python 서버 코드만으로 완결
- 별도 빌드 파이프라인 없음
- 동적 업데이트는 HTMX로 처리 (페이지 리로드 없이 부분 갱신)

**이후 전환 가능: React SPA**
- FastAPI는 JSON API만 제공 (변경 없음)
- React 앱이 API 호출
- 더 풍부한 UX 필요 시 전환

---

## 빌드 순서

### Step 1: 기반 구축

- `pyproject.toml`에 `fastapi`, `uvicorn`, `sqlalchemy` 추가
- `server/` 디렉토리 구조 생성
- `config.py`: 스토리지 경로, DB 경로 설정
- `db/engine.py`: SQLite 연결, `projects` 테이블 생성
- `server/main.py`: FastAPI 앱 기본 구성, 에러 핸들러 등록

검증: `uvicorn server.main:app` 실행 후 `/docs` Swagger 접근 확인

### Step 2: 프로젝트 API

- `ProjectService` 구현
- `routers/projects.py`: GET/POST/DELETE `/api/projects`
- `schemas/projects.py`: 요청/응답 모델

검증: Swagger UI에서 프로젝트 생성 → `.pvm/` 디렉토리 생성 확인

### Step 3: 프롬프트 API

- `PromptService` 구현
- `routers/prompts.py`: 전체 프롬프트 엔드포인트
- `schemas/prompts.py`: AddPromptRequest, DeployRequest 등

검증: Swagger UI에서 YAML 추가 → deploy → rollback 전체 플로우 확인

### Step 4: 스냅샷 API

- `SnapshotService` 구현
- `routers/snapshots.py`: 전체 스냅샷 엔드포인트

검증: 스냅샷 생성 → 조회 → diff 확인

### Step 5: 기본 UI

- 레이아웃 템플릿 (`base.html`)
- 프로젝트 목록/생성 페이지
- 프롬프트 목록 + 버전 타임라인
- Deploy / Rollback 버튼 (HTMX로 비동기 처리)

### Step 6: Diff UI + 스냅샷 UI

- 버전 diff 뷰어
- 스냅샷 목록 + manifest 뷰
- 스냅샷 간 diff 뷰

---

## 실행

```bash
# 의존성 설치
poetry install -E server

# 서버 실행
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload

# Swagger UI 접근
http://localhost:8080/docs
```

---

## 향후 확장 (Phase 2)

협업 기능 추가 시 서비스 레이어만 확장한다. API 엔드포인트와 UI는 최소 변경으로 유지된다.

- `users`, `project_members`, `proposals` 테이블 추가
- `pvm propose`, `pvm review` 엔드포인트 추가
- `deploy` 엔드포인트에 proposal 승인 여부 체크 추가
- git 기반 push/pull 연동 (선택)

자세한 내용은 `COLLABORATION_DESIGN.md` 참고 (추후 작성).
