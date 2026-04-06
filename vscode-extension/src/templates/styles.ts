export function getStyles(): string {
  return `
    :root {
      --bg: var(--vscode-editor-background);
      --card: rgba(255, 255, 255, 0.04);
      --muted: var(--vscode-descriptionForeground);
      --text: var(--vscode-foreground);
      --border: var(--vscode-panel-border, rgba(127, 127, 127, 0.25));
      --green: #16a34a;
      --green-soft: rgba(22, 163, 74, 0.12);
      --blue: #2563eb;
      --blue-soft: rgba(37, 99, 235, 0.12);
      --yellow: #ca8a04;
      --yellow-soft: rgba(202, 138, 4, 0.14);
      --red: #dc2626;
      --red-soft: rgba(220, 38, 38, 0.12);
      --gray-soft: rgba(148, 163, 184, 0.12);
      --shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
      --radius: 14px;
      --font-mono: var(--vscode-editor-font-family, Consolas, monospace);
      --font-sans: var(--vscode-font-family, "Segoe UI", sans-serif);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 24px;
      background: radial-gradient(circle at top right, rgba(22,163,74,0.10), transparent 30%), var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.45;
    }
    a { color: var(--green); text-decoration: none; cursor: pointer; }
    a:hover { text-decoration: underline; }
    h1, h2, h3, h4, p { margin: 0; }
    h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.03em; }
    h3 { font-size: 13px; font-weight: 700; color: var(--muted); letter-spacing: 0.08em; }
    .brand { display:flex; align-items:center; gap:10px; margin-bottom:6px; }
    .brand-logo {
      height: 32px;
      width: auto;
      display: block;
    }
    .brand-mark {
      width: 28px;
      height: 28px;
      display:flex;
      align-items:center;
      justify-content:center;
      border-radius: 8px;
      background: linear-gradient(135deg, #22c55e, #15803d);
      color: white;
      font-weight: 900;
      font-family: var(--font-mono);
      box-shadow: 0 10px 24px rgba(21, 128, 61, 0.28);
    }
    .brand-word {
      color: var(--green);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.22em;
      text-transform: uppercase;
    }
    .space-y > * + * { margin-top: 20px; }
    .grid { display: grid; gap: 16px; }
    .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .dashboard-grid { align-items: stretch; grid-auto-rows: 1fr; align-content: stretch; }
    .dashboard-grid > .card,
    .dashboard-card {
      height: 100%;
      display: flex;
      flex-direction: column;
      min-height: 340px;
    }
    .dashboard-card-body {
      flex: 1 1 auto;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
    }
    .grid-sidebar { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 20px; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 20px;
    }
    .card + .card { margin-top: 16px; }
    .flex { display: flex; align-items: center; gap: 10px; }
    .flex-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .wrap { flex-wrap: wrap; }
    .stack > * + * { margin-top: 12px; }
    .mono { font-family: var(--font-mono); }
    .text-muted { color: var(--muted); }
    .text-xs { font-size: 12px; }
    .text-sm { font-size: 13px; }
    .stat-number { font-size: 32px; font-weight: 800; color: var(--green); letter-spacing: -0.04em; }
    .button {
      border: 1px solid transparent;
      border-radius: 10px;
      padding: 9px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: 120ms ease;
    }
    .button:hover { transform: translateY(-1px); }
    .button-primary { background: var(--green); color: white; }
    .button-secondary { background: var(--gray-soft); color: var(--text); border-color: var(--border); }
    .button-warning { background: var(--yellow-soft); color: var(--yellow); border-color: rgba(202, 138, 4, 0.24); }
    .button-danger { background: var(--red-soft); color: var(--red); border-color: rgba(220, 38, 38, 0.24); }
    .button-link { background: transparent; border: none; color: var(--green); padding: 0; }
    .badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }
    .badge-green { background: var(--green-soft); color: var(--green); }
    .badge-blue { background: var(--blue-soft); color: var(--blue); }
    .badge-yellow { background: var(--yellow-soft); color: var(--yellow); }
    .badge-red { background: var(--red-soft); color: var(--red); }
    .badge-gray { background: var(--gray-soft); color: var(--muted); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 12px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
    tr:last-child td { border-bottom: none; }
    .clickable-row { cursor: pointer; }
    .clickable-row:hover { background: rgba(255, 255, 255, 0.03); }
    .code-block {
      font-family: var(--font-mono);
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(15, 23, 42, 0.45);
      color: #e2e8f0;
      border-radius: 12px;
      padding: 16px;
      overflow: auto;
      font-size: 12px;
      line-height: 1.6;
    }
    input, textarea, select {
      width: 100%;
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
    }
    textarea { min-height: 140px; resize: vertical; font-family: var(--font-mono); }
    label { display: block; font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 6px; letter-spacing: 0.04em; text-transform: uppercase; }
    .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
    .tab { background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--muted); cursor: pointer; padding: 10px 14px; font-size: 13px; font-weight: 700; }
    .tab.active { color: var(--green); border-bottom-color: var(--green); }
    .hidden { display: none !important; }
    .notice { padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border); font-size: 13px; }
    .notice-warning { background: var(--yellow-soft); color: var(--yellow); border-color: rgba(202, 138, 4, 0.24); }
    .notice-error { background: var(--red-soft); color: var(--red); border-color: rgba(220, 38, 38, 0.24); }
    .version-list { display: grid; gap: 8px; }
    .version-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; cursor: pointer; }
    .version-item.active { border-color: rgba(22, 163, 74, 0.45); background: var(--green-soft); }
    .kv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .kv-item .value { margin-top: 4px; font-size: 13px; }
    .section-title { margin-bottom: 12px; }
    .summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .summary-tile { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 16px; text-align: center; }
    .summary-tile .count { font-size: 34px; font-weight: 800; letter-spacing: -0.04em; }
    .mt-2 { margin-top: 8px; }
    .mt-3 { margin-top: 12px; }
    .mt-4 { margin-top: 16px; }
    .mt-5 { margin-top: 20px; }
    @media (max-width: 960px) {
      body { padding: 16px; }
      .grid-2, .grid-3, .grid-sidebar, .summary-grid, .kv-grid { grid-template-columns: 1fr; }
    }
  `;
}
