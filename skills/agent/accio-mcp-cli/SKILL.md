---
name: accio-mcp-cli
description: Use the accio-mcp-cli command-line tool to discover, search, and invoke MCP tools (Twitter, Gmail, Notion, Square, Apify, etc.) directly from the terminal. Use when the user asks to call MCP tools via CLI, run accio-mcp-cli commands, list available MCP tools from the command line, or invoke remote service integrations from the shell instead of an in-app MCP gateway.
---

# accio-mcp-cli

CLI tool for discovering, searching, and invoking MCP tools.
Authentication is automatic — no tokens or credentials needed.

## Recommended Workflow

**Use `toolkit` to browse and discover toolkits, `search` to find tools, then `call` to invoke.** Do NOT use `list` — it returns 150+ tools and floods context.

```bash
accio-mcp-cli toolkit                                       # Step 1: discover all toolkits
accio-mcp-cli toolkit square                                # Step 2: list tools under a toolkit
accio-mcp-cli search twitter                                # or search tools by keyword
accio-mcp-cli call search_twitter --query "AI agent" --count 5  # Step 3: call the tool
```

## Commands

### search \<keyword\> (preferred — use this first)

Full-text search across **all tools** (Phoenix + Composio + custom MCP servers).
Matches: name, description, `meta.toolkit`, `meta.toolkit_service`. Falls back to server-side toolkit/service search when no client-side matches. Gives fuzzy suggestions on zero matches.

Alias: `keyword`

```bash
accio-mcp-cli search twitter
```

### toolkit [keyword]

Browse toolkit structure or filter by toolkit name. **Phoenix remote tools only.**
No keyword → toolkit overview. With keyword → all tools under matching toolkit/service.

Alias: `toolkits`

```bash
accio-mcp-cli toolkit                 # toolkit overview
accio-mcp-cli toolkit gmail           # tools under gmail service
```

### call \<tool-name\> [args]

Invoke a tool. Alias: `run`

```bash
accio-mcp-cli call search_twitter --query "AI" --count 5
accio-mcp-cli call post_tweet --json '{"text": "Hello!"}'
```

**Argument rules:**
- `--json '{...}'` takes precedence
- `--key value` → `{ key: value }` (`true`/`false` → bool, digits → int)
- `--flag` (no value) → `{ flag: true }`
- `--port`, `--json`, `--raw`, `--refresh`, `--help` are excluded from tool args

Output extracts `text` content from MCP results. Use `--raw` for full JSON.

### list

List all 150+ tools. Prefer `search`/`toolkit`. Alias: `ls`

### Global Options

| Flag | Description |
|------|-------------|
| `--port <port>` | Gateway port (default: 4097) |
| `--raw` | Raw JSON output |
| `--refresh` | Force refresh tools cache |
| `-h, --help` | Help |

## Notes

1. **Always use `search` first** — don't guess tool names. Use `toolkit` to browse available toolkits.
2. **Auth** — most services need a one-time `start_*_auth` call.
3. **Timeout** — 60s; long-running tools may need `--raw` and manual polling.
4. **Unknown commands** — error. Must use `search`, `toolkit`, `call`, or `list`.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Cannot connect to Gateway` | Ensure Accio Desktop is running |
| `Route not found` | Restart Accio Desktop to load proxy route |
| `Request timed out` | Retry; some tools are slow |
| Auth error | Run `start_*_auth` first |
| Tool not found | Use `search <name>` to find correct name |
