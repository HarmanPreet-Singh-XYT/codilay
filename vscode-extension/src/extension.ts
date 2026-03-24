/**
 * CodiLay VSCode Extension
 *
 * Surfaces codebase documentation inline alongside the file being edited.
 * Connects to a running CodiLay server (codilay serve .) to fetch
 * documentation sections, dependency graph data, and chat answers.
 */

import * as vscode from "vscode";

// ── Types ────────────────────────────────────────────────────────────────────

interface Section {
  id: string;
  title: string;
  file: string;
  tags: string[];
  content: string;
}

interface ChatResponse {
  answer: string;
  sources: string[];
  confidence: number;
  escalated: boolean;
  conversation_id: string;
  message_id: string;
}

interface SearchResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string;
  role: string;
  snippet: string;
  score: number;
}

interface Stats {
  project: string;
  files_processed: number;
  sections: number;
  closed_wires: number;
  open_wires: number;
  last_commit: string;
  last_run: string;
}

interface TeamFact {
  id: string;
  fact: string;
  category: string;
  author: string;
  tags: string[];
  votes: number;
}

interface TeamDecision {
  id: string;
  title: string;
  description: string;
  status: string;
  author: string;
  related_files: string[];
}

interface TeamConvention {
  id: string;
  name: string;
  description: string;
  examples: string[];
  author: string;
}

interface WireNode {
  id: string;
  label?: string;
  file?: string;
  layer?: string;
}

interface WireEdge {
  source: string;
  target: string;
  type?: string;
}

interface CommitDoc {
  hash: string;
  filename: string;
  date: string;
  message: string;
  mtime: number;
}

interface AuditEntry {
  type: string;
  mode: string;
  timestamp: string;
  filename: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function getServerUrl(): string {
  const config = vscode.workspace.getConfiguration("codilay");
  return config.get<string>("serverUrl", "http://127.0.0.1:8484");
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${getServerUrl()}${path}`;
  const resp = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`CodiLay API error (${resp.status}): ${text}`);
  }
  return resp.json() as Promise<T>;
}

// ── Section Tree Provider ────────────────────────────────────────────────────

class SectionTreeItem extends vscode.TreeItem {
  constructor(
    public readonly section: Section,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState
  ) {
    super(section.title, collapsibleState);
    this.tooltip = `${section.title}\n${section.file || "No file"}`;
    this.description = section.file || "";
    this.contextValue = "section";
    this.command = {
      command: "codilay.openSection",
      title: "Open Section",
      arguments: [section],
    };
  }
}

class SectionTreeProvider
  implements vscode.TreeDataProvider<SectionTreeItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    SectionTreeItem | undefined | null
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private sections: Section[] = [];

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  async load(): Promise<void> {
    try {
      const data = await apiFetch<{ sections: Section[] }>("/api/sections");
      this.sections = data.sections;
      this.refresh();
    } catch {
      this.sections = [];
      this.refresh();
    }
  }

  getTreeItem(element: SectionTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): SectionTreeItem[] {
    return this.sections.map(
      (s) =>
        new SectionTreeItem(s, vscode.TreeItemCollapsibleState.None)
    );
  }

  getSectionForFile(filePath: string): Section | undefined {
    const rel = vscode.workspace.asRelativePath(filePath);
    return this.sections.find((s) => s.file === rel);
  }
}

// ── Team Tree Provider ───────────────────────────────────────────────────────

type TeamCategory = "facts" | "decisions" | "conventions";

class TeamTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly category: TeamCategory | null,
    public readonly detail: string,
    collapsibleState: vscode.TreeItemCollapsibleState
  ) {
    super(label, collapsibleState);
    this.tooltip = detail;
    if (category === null) {
      // leaf item
      this.description = detail.length > 60 ? detail.slice(0, 60) + "…" : detail;
    }
  }
}

class TeamTreeProvider implements vscode.TreeDataProvider<TeamTreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    TeamTreeItem | undefined | null
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private facts: TeamFact[] = [];
  private decisions: TeamDecision[] = [];
  private conventions: TeamConvention[] = [];

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  async load(): Promise<void> {
    try {
      const [f, d, c] = await Promise.all([
        apiFetch<{ facts: TeamFact[] }>("/api/team/facts"),
        apiFetch<{ decisions: TeamDecision[] }>("/api/team/decisions"),
        apiFetch<{ conventions: TeamConvention[] }>("/api/team/conventions"),
      ]);
      this.facts = f.facts;
      this.decisions = d.decisions;
      this.conventions = c.conventions;
    } catch {
      this.facts = [];
      this.decisions = [];
      this.conventions = [];
    }
    this.refresh();
  }

  getTreeItem(element: TeamTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: TeamTreeItem): TeamTreeItem[] {
    if (!element) {
      return [
        new TeamTreeItem(
          `Facts (${this.facts.length})`,
          "facts",
          "Team facts",
          vscode.TreeItemCollapsibleState.Collapsed
        ),
        new TeamTreeItem(
          `Decisions (${this.decisions.length})`,
          "decisions",
          "Team decisions",
          vscode.TreeItemCollapsibleState.Collapsed
        ),
        new TeamTreeItem(
          `Conventions (${this.conventions.length})`,
          "conventions",
          "Coding conventions",
          vscode.TreeItemCollapsibleState.Collapsed
        ),
      ];
    }

    if (element.category === "facts") {
      return this.facts.map(
        (f) =>
          new TeamTreeItem(
            f.fact.length > 50 ? f.fact.slice(0, 50) + "…" : f.fact,
            null,
            `[${f.category}] ${f.fact}${f.author ? " — " + f.author : ""}`,
            vscode.TreeItemCollapsibleState.None
          )
      );
    }
    if (element.category === "decisions") {
      return this.decisions.map(
        (d) =>
          new TeamTreeItem(
            d.title,
            null,
            `[${d.status}] ${d.description}${d.author ? " — " + d.author : ""}`,
            vscode.TreeItemCollapsibleState.None
          )
      );
    }
    if (element.category === "conventions") {
      return this.conventions.map(
        (c) =>
          new TeamTreeItem(
            c.name,
            null,
            c.description,
            vscode.TreeItemCollapsibleState.None
          )
      );
    }

    return [];
  }
}

// ── Wires Tree Provider ──────────────────────────────────────────────────────

class WireTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly isCategory: boolean,
    description: string,
    collapsibleState: vscode.TreeItemCollapsibleState
  ) {
    super(label, collapsibleState);
    this.description = description;
    if (!isCategory) {
      this.iconPath = new vscode.ThemeIcon("arrow-right");
    }
  }
}

class WiresTreeProvider implements vscode.TreeDataProvider<WireTreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    WireTreeItem | undefined | null
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private nodes: WireNode[] = [];
  private edges: WireEdge[] = [];
  private currentFile: string | undefined;

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  async load(filePath?: string): Promise<void> {
    this.currentFile = filePath;
    try {
      const body: Record<string, unknown> = {};
      if (filePath) {
        const rel = vscode.workspace.asRelativePath(filePath);
        body.modules = [rel];
      }
      const data = await apiFetch<{ nodes: WireNode[]; edges: WireEdge[] }>(
        "/api/graph/filter",
        { method: "POST", body: JSON.stringify(body) }
      );
      this.nodes = data.nodes || [];
      this.edges = data.edges || [];
    } catch {
      this.nodes = [];
      this.edges = [];
    }
    this.refresh();
  }

  getTreeItem(element: WireTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: WireTreeItem): WireTreeItem[] {
    if (!element) {
      const label = this.currentFile
        ? `Wires for ${vscode.workspace.asRelativePath(this.currentFile)}`
        : "All Wires";
      return [
        new WireTreeItem(
          label,
          true,
          `${this.nodes.length} nodes · ${this.edges.length} edges`,
          vscode.TreeItemCollapsibleState.Expanded
        ),
      ];
    }

    if (element.isCategory) {
      return this.edges.slice(0, 100).map((e) => {
        const src = this.nodes.find((n) => n.id === e.source);
        const tgt = this.nodes.find((n) => n.id === e.target);
        const srcLabel = src?.label || src?.file || e.source;
        const tgtLabel = tgt?.label || tgt?.file || e.target;
        return new WireTreeItem(
          srcLabel,
          false,
          `→ ${tgtLabel}`,
          vscode.TreeItemCollapsibleState.None
        );
      });
    }

    return [];
  }
}

// ── Webview Panel for Documentation ──────────────────────────────────────────

let docPanel: vscode.WebviewPanel | undefined;

function showDocPanel(
  context: vscode.ExtensionContext,
  content: string,
  title: string
): void {
  if (docPanel) {
    docPanel.title = title;
    docPanel.webview.html = getDocHtml(content, title);
    docPanel.reveal(vscode.ViewColumn.Beside);
  } else {
    docPanel = vscode.window.createWebviewPanel(
      "codilayDoc",
      title,
      vscode.ViewColumn.Beside,
      { enableScripts: false, retainContextWhenHidden: true }
    );
    docPanel.webview.html = getDocHtml(content, title);
    docPanel.onDidDispose(() => {
      docPanel = undefined;
    });
  }
}

function getDocHtml(content: string, title: string): string {
  const escaped = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const html = escaped
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");

  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      padding: 16px;
      line-height: 1.6;
    }
    h1, h2, h3 { color: var(--vscode-textLink-foreground); }
    code {
      background: var(--vscode-textCodeBlock-background);
      padding: 2px 4px;
      border-radius: 3px;
      font-family: var(--vscode-editor-font-family);
    }
    .meta { color: var(--vscode-descriptionForeground); font-size: 0.9em; }
  </style>
</head>
<body>
  <h1>${title}</h1>
  <div>${html}</div>
</body>
</html>`;
}

// ── Inline Documentation Decorations ─────────────────────────────────────────

const docDecorationType = vscode.window.createTextEditorDecorationType({
  after: {
    color: "#888888",
    fontStyle: "italic",
    margin: "0 0 0 1em",
  },
});

async function updateInlineHints(
  editor: vscode.TextEditor,
  sectionProvider: SectionTreeProvider
): Promise<void> {
  const config = vscode.workspace.getConfiguration("codilay");
  if (!config.get<boolean>("inlineHints", true)) {
    editor.setDecorations(docDecorationType, []);
    return;
  }

  const section = sectionProvider.getSectionForFile(editor.document.fileName);
  if (!section || !section.content) {
    editor.setDecorations(docDecorationType, []);
    return;
  }

  const decoration: vscode.DecorationOptions = {
    range: new vscode.Range(0, 0, 0, 0),
    renderOptions: {
      after: {
        contentText: ` CodiLay: ${section.title}`,
      },
    },
  };

  editor.setDecorations(docDecorationType, [decoration]);
}

// ── Status Bar ────────────────────────────────────────────────────────────────

function createStatusBar(): vscode.StatusBarItem {
  const item = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  item.command = "codilay.showDocPanel";
  item.tooltip = "CodiLay: Show documentation panel";
  item.text = "$(book) CodiLay";
  item.show();
  return item;
}

async function refreshStatusBar(item: vscode.StatusBarItem): Promise<void> {
  try {
    const stats = await apiFetch<Stats>("/api/stats");
    const openWires = stats.open_wires > 0 ? ` · ${stats.open_wires} open` : "";
    item.text = `$(book) ${stats.sections} sections${openWires}`;
    item.tooltip = `CodiLay — ${stats.project}\n${stats.files_processed} files · ${stats.closed_wires} closed wires${openWires ? "\n" + stats.open_wires + " open wires" : ""}`;
  } catch {
    item.text = "$(book) CodiLay";
  }
}

// ── Chat Session ─────────────────────────────────────────────────────────────

let activeChatConversationId: string | undefined;

// ── Activation ───────────────────────────────────────────────────────────────

const AUDIT_TYPES: Record<string, string> = {
  security: "Security",
  code_quality: "Code Quality",
  performance: "Performance",
  architecture: "Architecture",
  business_logic: "Business Logic",
  appsec: "Application Security",
  api_sec: "API Security",
  authz: "Auth & Authorization",
  secrets: "Secrets Management",
  dependencies: "Dependency / Supply Chain",
  testing: "Testing Coverage",
  observability: "Observability",
  compliance: "Compliance",
  database: "Database",
  data_privacy: "Data Privacy",
  cost: "Cost (FinOps)",
};

export function activate(context: vscode.ExtensionContext): void {
  const sectionProvider = new SectionTreeProvider();
  const teamProvider = new TeamTreeProvider();
  const wiresProvider = new WiresTreeProvider();

  // Register tree views
  vscode.window.registerTreeDataProvider("codilay.sections", sectionProvider);
  vscode.window.registerTreeDataProvider("codilay.team", teamProvider);
  vscode.window.registerTreeDataProvider("codilay.wires", wiresProvider);

  // Status bar
  const statusBar = createStatusBar();
  context.subscriptions.push(statusBar);

  // Initial load
  sectionProvider.load();
  teamProvider.load();
  wiresProvider.load();
  refreshStatusBar(statusBar);

  // ── Commands ─────────────────────────────────────────────────────

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.showDocPanel", async () => {
      try {
        const data = await apiFetch<{ markdown: string }>("/api/document");
        showDocPanel(context, data.markdown, "CodiLay Documentation");
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.showFileDoc", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showInformationMessage("No active file.");
        return;
      }
      const section = sectionProvider.getSectionForFile(
        editor.document.fileName
      );
      if (section) {
        showDocPanel(context, section.content, section.title);
      } else {
        vscode.window.showInformationMessage(
          "No documentation found for this file."
        );
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.openSection", (section: Section) => {
      showDocPanel(context, section.content, section.title);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.askQuestion", async () => {
      const continuingConv = !!activeChatConversationId;
      const question = await vscode.window.showInputBox({
        prompt: continuingConv
          ? "Ask a follow-up (conversation active)"
          : "Ask CodiLay about your codebase",
        placeHolder: "How does the authentication flow work?",
      });
      if (!question) {
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "CodiLay is thinking...",
          cancellable: false,
        },
        async () => {
          try {
            const body: Record<string, unknown> = { question };
            if (activeChatConversationId) {
              body.conversation_id = activeChatConversationId;
            }
            const resp = await apiFetch<ChatResponse>("/api/chat", {
              method: "POST",
              body: JSON.stringify(body),
            });
            activeChatConversationId = resp.conversation_id;
            showDocPanel(
              context,
              resp.answer +
                (resp.escalated ? "\n\n---\n*Deep agent was used*" : "") +
                (resp.sources.length
                  ? `\n\n---\n*Sources: ${resp.sources.join(", ")}*`
                  : ""),
              "Chat Answer"
            );
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            vscode.window.showErrorMessage(`CodiLay: ${msg}`);
          }
        }
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.newConversation", () => {
      activeChatConversationId = undefined;
      vscode.window.showInformationMessage("CodiLay: Started a new conversation.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.searchConversations", async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search past conversations",
        placeHolder: "database migration",
      });
      if (!query) {
        return;
      }

      try {
        const data = await apiFetch<{
          results: SearchResult[];
        }>(`/api/search?q=${encodeURIComponent(query)}&top_k=10`);

        if (!data.results.length) {
          vscode.window.showInformationMessage(`No results for "${query}".`);
          return;
        }

        const items = data.results.map((r) => ({
          label: `${r.role === "user" ? "You" : "CodiLay"}: ${r.snippet.slice(0, 80)}`,
          description: r.conversation_title,
          detail: `Score: ${r.score.toFixed(2)}`,
        }));

        const selected = await vscode.window.showQuickPick(items, {
          placeHolder: `${data.results.length} results`,
        });

        if (selected) {
          const idx = items.indexOf(selected);
          const result = data.results[idx];
          showDocPanel(context, result.snippet, "Search Result");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.showGraph", async () => {
      try {
        const data = await apiFetch<{ nodes: WireNode[]; edges: WireEdge[] }>(
          "/api/graph/filter",
          {
            method: "POST",
            body: JSON.stringify({}),
          }
        );
        showDocPanel(
          context,
          `# Dependency Graph\n\n` +
            `**${(data.nodes || []).length} nodes, ${(data.edges || []).length} edges**\n\n` +
            `Use the web UI (\`codilay serve .\`) for an interactive graph view.`,
          "Dependency Graph"
        );
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.showDocDiff", async () => {
      try {
        const data = await apiFetch<{
          has_changes: boolean;
          message?: string;
          added?: string[];
          removed?: string[];
          modified?: string[];
          summary?: string;
        }>("/api/doc-diff");

        if (!data.has_changes) {
          vscode.window.showInformationMessage(
            `CodiLay: ${data.message || "No changes since last run."}`
          );
          return;
        }

        const lines: string[] = ["# Documentation Diff\n"];
        if (data.summary) {
          lines.push(data.summary + "\n");
        }
        if (data.added?.length) {
          lines.push(`## Added (${data.added.length})`);
          data.added.forEach((s) => lines.push(`- ${s}`));
          lines.push("");
        }
        if (data.modified?.length) {
          lines.push(`## Modified (${data.modified.length})`);
          data.modified.forEach((s) => lines.push(`- ${s}`));
          lines.push("");
        }
        if (data.removed?.length) {
          lines.push(`## Removed (${data.removed.length})`);
          data.removed.forEach((s) => lines.push(`- ${s}`));
          lines.push("");
        }

        showDocPanel(context, lines.join("\n"), "Doc Diff");
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.showCommitDocs", async () => {
      try {
        const data = await apiFetch<{ docs: CommitDoc[] }>("/api/commit-docs");

        if (!data.docs.length) {
          vscode.window.showInformationMessage(
            "CodiLay: No commit docs found. Run `codilay commit-doc .` first."
          );
          return;
        }

        const items = data.docs.map((d) => ({
          label: d.hash,
          description: d.message || "(no message)",
          detail: d.date,
          doc: d,
        }));

        const selected = await vscode.window.showQuickPick(items, {
          placeHolder: `${data.docs.length} commit docs`,
          matchOnDescription: true,
        });

        if (!selected) {
          return;
        }

        const result = await apiFetch<{ hash: string; content: string }>(
          `/api/commit-docs/${selected.doc.hash}`
        );
        showDocPanel(context, result.content, `Commit ${result.hash}`);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "codilay.annotateFile",
      async (uri?: vscode.Uri) => {
        const editor = vscode.window.activeTextEditor;
        const filePath = uri?.fsPath ?? editor?.document.fileName;
        if (!filePath) {
          vscode.window.showInformationMessage("No file selected.");
          return;
        }

        // Capture selection range when invoked from the editor with text selected
        let lineRange: string | undefined;
        if (editor && editor.document.fileName === filePath && !editor.selection.isEmpty) {
          const start = editor.selection.start.line + 1;
          const end = editor.selection.end.line + 1;
          lineRange = start === end ? `${start}` : `${start}:${end}`;
        }

        const promptSuffix = lineRange ? ` (lines ${lineRange})` : "";
        const note = await vscode.window.showInputBox({
          prompt: `Add annotation to ${vscode.workspace.asRelativePath(filePath)}${promptSuffix}`,
          placeHolder: "This file handles X — be careful about Y",
        });
        if (!note) {
          return;
        }

        const author = await vscode.window.showInputBox({
          prompt: "Your name (optional)",
          placeHolder: "Leave blank to skip",
        });

        try {
          await apiFetch("/api/team/annotations", {
            method: "POST",
            body: JSON.stringify({
              file_path: vscode.workspace.asRelativePath(filePath),
              note,
              author: author || "",
              ...(lineRange ? { line_range: lineRange } : {}),
            }),
          });
          vscode.window.showInformationMessage("CodiLay: Annotation saved.");
          teamProvider.load();
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          vscode.window.showErrorMessage(`CodiLay: ${msg}`);
        }
      }
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.addTeamFact", async () => {
      const fact = await vscode.window.showInputBox({
        prompt: "Add a team fact",
        placeHolder: "We use UUID v4 for all primary keys",
      });
      if (!fact) {
        return;
      }

      const category = await vscode.window.showQuickPick(
        ["general", "architecture", "security", "performance", "convention"],
        { placeHolder: "Category" }
      );

      try {
        await apiFetch("/api/team/facts", {
          method: "POST",
          body: JSON.stringify({ fact, category: category || "general" }),
        });
        vscode.window.showInformationMessage("CodiLay: Fact added.");
        teamProvider.load();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`CodiLay: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.runAudit", async () => {
      const typeItems = Object.entries(AUDIT_TYPES).map(([key, label]) => ({
        label,
        description: key,
      }));

      const selectedType = await vscode.window.showQuickPick(typeItems, {
        placeHolder: "Select audit type",
      });
      if (!selectedType) {
        return;
      }

      const mode = await vscode.window.showQuickPick(["quick", "standard", "deep"], {
        placeHolder: "Audit depth",
      });
      if (!mode) {
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `CodiLay: Running ${selectedType.label} audit…`,
          cancellable: false,
        },
        async () => {
          try {
            const result = await apiFetch<{ summary?: string; findings?: string; content?: string }>(
              "/api/audits",
              {
                method: "POST",
                body: JSON.stringify({
                  audit_type: selectedType.description,
                  mode,
                }),
              }
            );
            const content =
              result.content ||
              result.summary ||
              result.findings ||
              JSON.stringify(result, null, 2);
            showDocPanel(context, content, `${selectedType.label} Audit`);
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            vscode.window.showErrorMessage(`CodiLay: ${msg}`);
          }
        }
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.openInBrowser", () => {
      vscode.env.openExternal(vscode.Uri.parse(getServerUrl()));
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codilay.refresh", () => {
      sectionProvider.load();
      teamProvider.load();
      wiresProvider.load(vscode.window.activeTextEditor?.document.fileName);
      refreshStatusBar(statusBar);
      vscode.window.showInformationMessage("CodiLay: Refreshed.");
    })
  );

  // ── Inline hints + wires on active editor change ──────────────

  if (vscode.window.activeTextEditor) {
    updateInlineHints(vscode.window.activeTextEditor, sectionProvider);
    wiresProvider.load(vscode.window.activeTextEditor.document.fileName);
  }

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        updateInlineHints(editor, sectionProvider);
        wiresProvider.load(editor.document.fileName);
      }
    })
  );

  // Refresh status bar every 60 seconds
  const statsTimer = setInterval(() => refreshStatusBar(statusBar), 60_000);
  context.subscriptions.push({ dispose: () => clearInterval(statsTimer) });
}

export function deactivate(): void {
  // Cleanup
}
