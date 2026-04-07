function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function text(value: unknown): string {
  return escapeHtml(String(value ?? ""));
}

export function card(title: string, body: string): string {
  return `
    <section class="card">
      <div class="section-title"><h3>${text(title)}</h3></div>
      ${body}
    </section>
  `;
}

function payloadAttribute(payload: Record<string, unknown>): string {
  return escapeHtml(JSON.stringify(payload));
}

export function actionButton(
  label: string,
  variant: "primary" | "secondary" | "warning" | "danger" | "link",
  action: string,
  payload: Record<string, unknown> = {},
): string {
  return `<button class="button button-${variant}" data-action="${text(action)}" data-payload="${payloadAttribute(payload)}">${text(label)}</button>`;
}

export function actionLink(
  label: string,
  action: string,
  payload: Record<string, unknown> = {},
  className = "",
): string {
  return `<a class="${text(className)}" href="#" data-action="${text(action)}" data-payload="${payloadAttribute(payload)}">${text(label)}</a>`;
}

export function badge(label: string, tone: "green" | "blue" | "yellow" | "red" | "gray"): string {
  return `<span class="badge badge-${tone}">${text(label)}</span>`;
}

export function codeBlock(content: string): string {
  return `<pre class="code-block">${escapeHtml(content)}</pre>`;
}

export function table(headers: string[], rows: string[][]): string {
  const head = headers.map((header) => `<th>${text(header)}</th>`).join("");
  const body = rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

export function clickableTable(
  headers: string[],
  rows: { cells: string[]; action: string; payload?: Record<string, unknown> }[],
): string {
  const head = headers.map((header) => `<th>${text(header)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr class="clickable-row" data-action="${text(row.action)}" data-payload="${payloadAttribute(row.payload ?? {})}">${row.cells
          .map((cell) => `<td>${cell}</td>`)
          .join("")}</tr>`,
    )
    .join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

export function select(
  id: string,
  options: Array<{ value: string; label: string; selected?: boolean }>,
): string {
  return `
    <select id="${text(id)}">
      ${options
        .map(
          (option) =>
            `<option value="${text(option.value)}"${option.selected ? " selected" : ""}>${text(option.label)}</option>`,
        )
        .join("")}
    </select>
  `;
}

export function emptyState(message: string): string {
  return `<div class="card"><p class="text-muted text-sm">${text(message)}</p></div>`;
}

export function keyValueGrid(entries: Array<{ key: string; value: string }>): string {
  return `
    <div class="kv-grid">
      ${entries
        .map(
          (entry) => `
            <div class="kv-item">
              <div class="text-muted text-xs">${text(entry.key)}</div>
              <div class="value">${entry.value}</div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

export function htmlPage(title: string, subtitle?: string, actions?: string, logoSrc?: string): string {
  return `
    <header class="flex-between wrap">
      <div class="stack">
        ${
          logoSrc
            ? `<div class="brand"><img class="brand-logo" src="${text(logoSrc)}" alt="pvm logo" /></div>`
            : `<div class="brand"><div class="brand-mark">P</div><div class="brand-word">pvm</div></div>`
        }
        <h1>${text(title)}</h1>
        ${subtitle ? `<p class="text-muted text-sm">${subtitle}</p>` : ""}
      </div>
      ${actions ? `<div class="flex wrap">${actions}</div>` : ""}
    </header>
  `;
}
