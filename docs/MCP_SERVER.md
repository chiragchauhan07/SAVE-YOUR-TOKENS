# MCP Server

Save your Tokens exposes its analysis engine and Knowledge Base generator
through the [Model Context Protocol](https://modelcontextprotocol.io), so
any MCP-compatible AI coding assistant can call it directly instead of
shelling out to the CLI.

The MCP layer is a thin adapter (`mcp_server/`) over the same engine the CLI
uses (`analyzer/`, `generator/`). It contains no analysis logic of its own —
see [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the layering, and
[docs/DECISIONS.md](DECISIONS.md) (D-034 through D-043) for the reasoning
behind specific choices below.

## Installation

Requires Python 3.11+.

```bash
python -m pip install "save-your-tokens[mcp]"
```

From source:

```bash
git clone https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS.git save-your-tokens
cd save-your-tokens
python -m pip install -e ".[dev]"
```

`[mcp]` (or `[dev]`, which includes it) pulls in the official
[MCP Python SDK](https://pypi.org/project/mcp/) — the project's only
runtime dependency, and only for this layer (D-039). The analysis engine
and Knowledge Base generator remain dependency-free.

## Running the server

```bash
python server.py
```

Or, once installed:

```bash
save-your-tokens-mcp
```

Both run the same server over **stdio transport** and are meant to be
launched by an MCP client, not run interactively — there is no terminal
output to watch for a healthy server; a client speaks JSON-RPC to it over
stdin/stdout.

## MCP client configuration

### Claude Code

Add to your MCP configuration (`.mcp.json`, or via `claude mcp add`):

```json
{
  "mcpServers": {
    "save-your-tokens": {
      "command": "save-your-tokens-mcp"
    }
  }
}
```

Or, running from a source checkout without installing:

```json
{
  "mcpServers": {
    "save-your-tokens": {
      "command": "python",
      "args": ["/absolute/path/to/save-your-tokens/server.py"]
    }
  }
}
```

### Other MCP clients

Any client that supports stdio-transport MCP servers (Claude Desktop,
Cursor, and others) can use the same `command`/`args` shape above — consult
your client's own documentation for where that configuration lives. This
server does not currently support SSE or streamable-HTTP transport (see
D-037); if your client requires a network transport, it isn't supported
yet.

## Supported clients

Any MCP client implementing the stdio transport. Tested directly against
the official Python MCP SDK's client (`mcp.client.stdio`) as part of this
project's own test suite (`tests/test_mcp_server.py::test_stdio_transport_end_to_end`),
which spawns the real server as a subprocess and exchanges real protocol
messages with it.

## Tools

Four tools, covering the full engine surface without a sprawling API.
Every tool response is a JSON object; error responses always have the
shape `{"success": false, "error": {"type": "...", "message": "..."}}` —
see [Error handling](#error-handling) below.

### `health_check`

No arguments. Returns package/SDK/environment version information —
useful for confirming an installation is wired up correctly.

```json
{
  "success": true,
  "status": "ok",
  "package_version": "0.4.0",
  "server_version": "0.4.0",
  "mcp_sdk_version": "1.28.1",
  "python_version": "3.12.4",
  "platform": "Windows-11-10.0.26200-SP0"
}
```

### `repository_summary`

The fast path: analyse a repository and get back a compact overview —
project type, languages, frameworks, entry points, routes, database
models, the top 20 important files, authentication and configuration. Does
**not** generate the Knowledge Base.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | required | Repository to analyse |

```json
{
  "success": true,
  "name": "sample_repo",
  "path": "/abs/path/sample_repo",
  "repository_type": {"name": "REST API", "confidence": "HIGH", "evidence": ["framework: Flask"]},
  "languages": [{"name": "Python", "file_count": 3, "size_bytes": 1329, "percentage": 100.0}],
  "frameworks": [{"name": "Flask", "confidence": "HIGH", "evidence": ["dependency: flask"]}],
  "entry_points": ["..."],
  "routes": ["..."],
  "database_models": [],
  "important_files": ["..."],
  "authentication": [],
  "configuration": ["..."]
}
```

### `analyze_repository`

The primary tool: everything `repository_summary` returns, and optionally
the Knowledge Base in the same call — analysed exactly once either way
(D-036).

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | required | Repository to analyse |
| `include_knowledge_base` | boolean | `false` | Also generate the Knowledge Base |
| `write_knowledge_base` | boolean | `false` | Also write it to disk (implies generation) |
| `output_dir` | string \| null | `<path>/.ai-context` | Where to write |
| `overwrite` | boolean | `true` | Overwrite an existing, non-empty output directory |

```json
{
  "success": true,
  "repository": { "...": "same shape as repository_summary" },
  "knowledge_base": {
    "written": true,
    "skipped": false,
    "output_directory": "/abs/path/.ai-context",
    "files": ["AI_CONTEXT.md", "..."],
    "total_bytes": 12345
  }
}
```

`knowledge_base` is only present when `include_knowledge_base` or
`write_knowledge_base` is `true`.

### `generate_knowledge_base`

Generate and write the `.ai-context/` Knowledge Base. Returns statistics —
file names and byte counts, **never document content** (D-040): a client
with filesystem access to the analysed repository reads the files
directly; echoing potentially tens of kilobytes of Markdown back through
the protocol on every call would be unnecessary work.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | required | Repository to analyse |
| `output_dir` | string \| null | `<path>/.ai-context` | Where to write |
| `overwrite` | boolean | `true` | Overwrite an existing, non-empty output directory |

```json
{
  "success": true,
  "written": true,
  "skipped": false,
  "output_directory": "/abs/path/.ai-context",
  "files": ["AI_CONTEXT.md", "API_ROUTES.md", "..."],
  "total_bytes": 12345
}
```

With `overwrite: false` against a directory that already has content:

```json
{
  "success": true,
  "written": false,
  "skipped": true,
  "reason": "Output directory already contains files and overwrite is False.",
  "output_directory": "/abs/path/.ai-context"
}
```

## Error handling

Every tool catches its own exceptions — none ever propagates to the client
as a raw traceback (D-035). `error.type` is one of:

| Type | Meaning |
|---|---|
| `repository_not_found` | The given path does not exist |
| `invalid_repository` | The path exists but is not a directory |
| `permission_denied` | The process could not read the repository or write the output directory |
| `analysis_failed` | An unexpected failure during scanning/identification/intelligence |
| `generation_failed` | An unexpected failure during Knowledge Base generation |
| `internal_error` | Anything else (health check failures, for instance) |

The real exception (with a full traceback) is always logged — to **stderr
only**, never stdout, since stdout carries the protocol stream on stdio
transport (D-038). Set `SAVE_YOUR_TOKENS_LOG_LEVEL=DEBUG` (or `INFO`) in
the server's environment for more detail while developing; the default is
`WARNING` (quiet).

## CLI usage

The CLI (`cli.py`) remains the primary command-line interface and is not
replaced by the MCP server — both call the same engine and generator
functions, so they always produce identical results for the same
repository (verified directly:
`tests/test_mcp_server.py::test_mcp_generated_knowledge_base_matches_cli_generated_knowledge_base`
byte-compares the two).

```bash
python cli.py scan /path/to/repo              # human-readable summary
python cli.py scan /path/to/repo --json        # full structured data
python cli.py generate /path/to/repo           # write .ai-context/
```

See the root [README.md](../README.md) for the full CLI reference.

## Limitations

- **stdio transport only** — no SSE or streamable-HTTP support yet (D-037).
- **Python repositories only** — the intelligence layer (entry points,
  routes, database models, imports) is Python-specific; other languages get
  Phase 1/2 results (files, languages, frameworks, package managers) but
  not Phase 3 intelligence. See `analyzer/intelligence/common.py`.
- **No streaming** — a tool call returns once analysis (and optionally
  generation) completes; there is no incremental progress reporting for
  large repositories yet.
- **No authentication or multi-tenancy** — this is a local, single-user
  server, the same trust model as any other local MCP server launched by a
  client.

## Architecture

See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the full layered diagram
and dependency rules. In short:

```
Repository → Scanner → Identification → Intelligence → Generator → MCP Integration Layer → AI Assistant
```

`mcp_server/` never re-scans, re-parses, or duplicates analysis logic — it
calls `analyzer.analyze_repository()` and `generator.generate_knowledge_base()`
directly and shapes their results into MCP tool responses.
