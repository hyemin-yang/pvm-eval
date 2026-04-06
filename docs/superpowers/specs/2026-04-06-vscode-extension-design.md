# PVM VS Code Extension Design Spec

## Overview

PVM(Prompt Versioning Manager)의 VS Code extension. 기존 Web UI(FastAPI + Jinja2 + Tailwind)의 기능과 페이지 구성을 그대로 VS Code 안으로 옮긴다. 스타일링은 VS Code 네이티브(vscode-webview-ui-toolkit).

## Architecture

- **TreeView** (사이드바): 프롬프트/스냅샷 탐색
- **WebView** (에디터 영역): 상세/diff/폼 등 각 페이지
- **CLI Wrapper**: `child_process.execFile`로 `pvm` CLI 실행, JSON 파싱
- **번들링**: esbuild

CLI가 이미 모든 명령에서 JSON을 출력하므로 별도 로직 불필요. Extension은 CLI를 호출하고 결과를 표시하는 thin client.

## Project Structure

```
prompt_versioning_manager/
└── vscode-extension/
    ├── package.json          # Extension manifest
    ├── tsconfig.json
    ├── esbuild.js
    ├── src/
    │   ├── extension.ts          # activate/deactivate
    │   ├── pvm-cli.ts            # CLI wrapper
    │   ├── views/
    │   │   ├── prompt-tree.ts    # 프롬프트 TreeView
    │   │   ├── snapshot-tree.ts  # 스냅샷 TreeView
    │   │   └── tree-items.ts     # TreeItem 정의
    │   ├── panels/
    │   │   ├── dashboard.ts      # 대시보드
    │   │   ├── prompt-detail.ts  # 프롬프트 상세
    │   │   ├── prompt-form.ts    # 프롬프트 추가/수정 폼
    │   │   ├── prompt-diff.ts    # 프롬프트 diff
    │   │   ├── snapshot-detail.ts# 스냅샷 상세
    │   │   ├── snapshot-diff.ts  # 스냅샷 diff
    │   │   ├── history.ts        # 히스토리
    │   │   └── setup.ts          # 프로젝트 init/destroy/reset
    │   ├── templates/
    │   │   └── *.ts              # HTML 생성 함수
    │   └── utils/
    │       ├── webview-utils.ts  # WebView 공통 유틸
    │       └── types.ts          # CLI JSON 응답 타입
    └── media/
        └── icon.svg
```

## Sidebar TreeView

Web UI 사이드바 네비게이션의 TreeView 변환:

```
PVM
├── Dashboard
├── Prompts
│   ├── prompt_id_1
│   │   ├── v1.0.0 (production)
│   │   ├── v1.0.1
│   │   └── v1.1.0
│   └── prompt_id_2
│       └── v1.0.0
├── Snapshots
│   ├── v1.0.0
│   └── v1.1.0
└── History
```

### Context Menu (우클릭)

- **Prompt ID**: Deploy, Rollback, Delete, Diff, Update
- **Version**: View Detail, Deploy This Version
- **Snapshot**: View Detail, Export, Diff

### Inline Actions (트리 항목 옆 아이콘)

- **Prompts 헤더**: Add Prompt
- **Snapshots 헤더**: Create Snapshot

### 동작

- 항목 클릭 → 해당 WebView 패널 열림
- 프로젝트 미초기화 시 → Setup 패널만 표시
- `pvm list`, `pvm snapshot list`로 트리 데이터 로딩

## WebView Panels (Web UI 1:1 매핑)

### Dashboard (`/` → `pvm.dashboard`)
- 프로젝트 트리 (code block), 프롬프트 수, 스냅샷 수, 최근 히스토리
- Init/Destroy/Reset 버튼 (프로젝트 미초기화 시 Init만 표시)
- CLI: `pvm project`, `pvm list`, `pvm snapshot list`, `pvm log`

### Prompt Detail (`/prompts/<id>` → `pvm.promptDetail`)
- 상단: ID, description, author, created_at
- 버전 목록 테이블 (production 배지)
- 선택된 버전의 LLM 설정, 프롬프트 내용 (코드 블록)
- Deploy, Rollback, Delete 버튼
- CLI: `pvm id <id> --info`, `pvm get <id> --version <v>`

### Prompt Form (`/prompts/add` → `pvm.promptForm`)
- 3가지 입력: 폼 직접 입력, 파일 업로드, YAML 에디터
- 수정 시 동일 폼 재활용
- CLI: `pvm add <template_path>`, `pvm template`

### Prompt Diff (`/prompts/<id>/diff` → `pvm.promptDiff`)
- 버전 두 개 선택 드롭다운
- diff2html unified/side-by-side 뷰
- 변경 통계 (lines added/removed, model config changed)
- CLI: `pvm diff <id> <from> <to>`

### Snapshot Detail (`/snapshots/<version>` → `pvm.snapshotDetail`)
- 매니페스트, checksum, 프롬프트 목록 테이블
- Export 버튼 (ZIP)
- CLI: `pvm snapshot get <version>`, `pvm snapshot export <version>`

### Snapshot Diff (`/snapshots/diff` → `pvm.snapshotDiff`)
- 두 버전 선택, added/removed/changed 표시
- CLI: `pvm snapshot diff <from> <to>`

### History (`/history` → `pvm.history`)
- 프롬프트/스냅샷 탭 전환
- 시간순 이벤트 목록
- CLI: `pvm log`

### Setup (프로젝트 미초기화 시)
- Init 폼 (프로젝트 이름 입력)
- Destroy/Reset (초기화된 프로젝트에서)
- CLI: `pvm init <name>`, `pvm destroy --force`, `pvm reset --force`

## CLI Wrapper (`pvm-cli.ts`)

```typescript
// 핵심 인터페이스
interface PvmCli {
  execute(command: string, args: string[]): Promise<any>;  // JSON 파싱된 결과
  // Prompt
  list(): Promise<PromptListResult>;
  get(id: string, version?: string): Promise<PromptGetResult>;
  info(id: string): Promise<PromptInfoResult>;
  add(templatePath: string, bump?: string): Promise<PromptAddResult>;
  deploy(id: string, version?: string): Promise<DeployResult>;
  rollback(id: string): Promise<RollbackResult>;
  delete(id: string): Promise<DeleteResult>;
  diff(id: string, from: string, to: string): Promise<DiffResult>;
  // Snapshot
  snapshotList(): Promise<string[]>;
  snapshotGet(version: string): Promise<SnapshotResult>;
  snapshotCreate(bump?: string): Promise<SnapshotResult>;
  snapshotExport(version: string, output?: string): Promise<ExportResult>;
  snapshotDiff(from: string, to: string): Promise<SnapshotDiffResult>;
  // Project
  init(name: string): Promise<InitResult>;
  destroy(): Promise<void>;
  reset(): Promise<void>;
  log(id?: string): Promise<LogEntry[]>;
  checkIntegrity(): Promise<IntegrityResult>;
  project(): Promise<string>;  // 프로젝트 트리 텍스트
}
```

- workspace root에서 `poetry run pvm` 실행
- stderr → VS Code error notification
- 비정상 exit code → 에러 처리

## Commands (package.json)

```
pvm.dashboard        대시보드 열기
pvm.addPrompt        프롬프트 추가
pvm.createSnapshot   스냅샷 생성
pvm.init             프로젝트 초기화
pvm.destroy          프로젝트 삭제
pvm.reset            프로젝트 리셋
pvm.refresh          트리뷰 새로고침
pvm.showHistory      히스토리 보기
```

## Error Handling

- PVM 프로젝트 미감지 시: "PVM 프로젝트가 없습니다. 초기화하시겠습니까?" notification
- CLI 실행 실패 시: stderr 메시지를 VS Code error notification으로 표시
- 파괴적 동작(destroy, delete, reset): VS Code 확인 다이얼로그 표시

## Testing

- CLI wrapper 단위 테스트 (mock child_process)
- TreeView 데이터 로딩 테스트
- WebView 메시지 핸들링 테스트

## Dependencies

- `@vscode/webview-ui-toolkit`: 네이티브 스타일 컴포넌트
- `diff2html`: diff 렌더링 (프롬프트 diff, 스냅샷 diff)
- esbuild: 번들링
- TypeScript
