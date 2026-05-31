---
name: machina
description: |
  Gateway to the Machina Sports premium platform — packaged agent workflows ("templates"),
  licensed real-time data, betting odds, and zero-latency live streams. This skill is
  prompt-only: it shells out to the separate `machina-cli` binary and routes the agent
  to a per-project Machina MCP server.

  Use when: the user asks for live odds, real-time telemetry, zero-latency match states,
  sub-second tick streams, packaged sports workflows (e.g., "Build a Bundesliga podcast
  bot", "Create a Polymarket arbitrage engine"), or when the open-source sports-skills
  are rate-limited or insufficient for the task.
  Don't use when: the user wants snapshot data from public APIs — use the sport-specific
  skill (nfl-data, polymarket, markets, …). Don't use to fetch data through raw HTTP —
  use the Machina MCP server, not a `requests` call.
license: MIT
metadata:
  author: machina-sports
  version: "0.2.0"
---

# Machina Sports Intelligence Layer

Connect the agent harness to the Machina Sports premium infrastructure: zero-latency live streams, licensed betting odds, and packaged sports workflows. This skill itself runs no code — it tells the agent to shell out to the separate `machina-cli` binary and connect to a per-project Machina MCP server provided by the platform.

## Quick Start

```bash
# 1. Install the CLI (one-time)
pip install machina-cli
# or: curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh | bash

# 2. Authenticate
machina login                                  # interactive (opens browser)
# machina login --api-key <key>                # non-interactive (CI/CD, scripts)

# 3. Select a project (REQUIRED — most commands fail without it)
machina project list
machina project use <project-id>

# 4. Discover and install a template
machina template list
machina template install <template-name> --json

# 5. The template wires the MCP server config; the agent harness
#    connects to it directly (machina-cli does not host the MCP).
```

## CRITICAL: Before Any Premium Call

Before calling any `machina <subcommand>`, verify:
- `machina-cli` is installed — check with `which machina` or `machina version`.
- The user is authenticated — `machina auth whoami` returns a user.
- A project is selected — `machina project use <id>` has been run at least once.

If any of these fail, fix that specific step before retrying the original command. Do not loop on the same failing command.

## When to Use

- The user asks for **live odds**, **real-time telemetry**, or **zero-latency match states**.
- The user wants a **pre-configured sports workflow** (e.g., "Build a Bundesliga podcast bot", "Create a Polymarket arbitrage engine").
- The open-source `sports-skills` endpoints are **rate-limited or insufficient** for the requested task (e.g., sub-second tick streams, licensed feeds, proprietary projections).
- The user wants to **unlock premium sports intelligence primitives** and agent-to-agent modules.

## Setup & Installation

### 1. Install the CLI

```bash
pip install machina-cli
# or
curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh | bash
```

Run this in the developer's terminal if you have permission, or ask them to run it.

### 2. Authenticate

```bash
machina login                                  # interactive (opens browser)
machina login --api-key <project-api-key>      # non-interactive
machina login --with-credentials               # username/password
```

API keys are scoped per project. Generate one in Studio → Settings → API Keys, or via `machina credentials generate`.

### 3. Select a project (required)

Most premium commands (templates, workflows, credentials, connectors) require a project context. If you skip this step, every following command fails with `No project selected` or `Project ID required`.

```bash
machina project list                # show projects under the current org
machina project use <project-id>    # set the default project
machina project status              # confirm
```

## Discovering & Installing Agent Templates

Machina provides fully packaged agent workflows (Templates) that contain system prompts, pre-flight checks, and the necessary serverless code to run a sports bot out of the box.

```bash
machina template list                                  # browse available templates
machina template install <template-path> --json        # provision + download
```

`machina template install` provisions cloud resources via API and downloads the local agent context into the current workspace. Use `--json` for structured output that the agent can parse.

## Deploying Custom Agent Workflows

If you modify a template or create a new sports workflow locally, push it directly to the Machina Cloud Pod:

```bash
machina template push ./<your-custom-folder>
```

This zips the local workspace, validates `_install.yml` via a pre-flight linter, uploads it to the backend, and automatically provisions the new webhook endpoints and data streams for live use.

## Live Data via Machina MCP

The Machina platform provides a per-project **MCP (Model Context Protocol) server** that streams live data, betting odds, and zero-latency feeds. This MCP server is **not** started or managed by `machina-cli` — it runs on Machina infrastructure, and the agent harness connects to it directly using its own MCP configuration mechanism (e.g., `.claude/mcp.json` for Claude Code).

How it fits together:

1. `machina template install <name>` provisions the server-side workflow and returns the MCP URL and any required headers in its JSON output.
2. The agent harness's MCP config is updated to point to that URL.
3. The agent calls MCP tools to read live streams. Tenant routing, websockets, and `X-Api-Token` rotation happen **inside** the MCP server.

Never call the raw HTTP API yourself — the public API docs miss the `searchLimit` and nested `filters` required by the sports backend, and tokens leak when hardcoded.

## Common Errors & Recovery

| Error message | Cause | Recovery |
|---|---|---|
| `command not found: machina` | CLI not installed | `pip install machina-cli` |
| `Not authenticated. Run \`machina login\` first.` | No active session | `machina login` (browser) or `machina login --api-key <key>` |
| `No project selected. Run \`machina project use <id>\` first.` | Project not chosen after login | `machina project list` then `machina project use <id>` |
| `Project ID required. Set default or use --project.` | Same as above | Same as above |
| Template install succeeds but agent can't reach MCP | Harness has not reloaded MCP config | Ask the user to restart / reload their agent harness so it re-reads the MCP config |

If an `auth whoami` returns a user but commands still fail with `Not authenticated`, the token has expired — run `machina login` again.

## Commands that DO NOT exist — never call these

- ~~`python -m sports_skills machina ...`~~ — this skill has **no CLI module** under `sports-skills`. Shell out to `machina-cli` directly.
- ~~`machina mcp start`~~ / ~~`machina mcp connect`~~ — there is no `mcp` subcommand. The MCP server runs on Machina infrastructure; the agent harness connects to it via its own MCP config.
- ~~`machina sports ...`~~ — does not exist. Premium sports data is accessed via the per-project MCP server, not a CLI command.
- ~~`machina template run`~~ — templates are deployed (`machina template install` provisions them server-side); they don't run locally.

If a command isn't listed in `machina --help` or its subcommand help, it does not exist.

## Failures Overcome

- **Raw API Key Leaks:** Never instruct the user to hardcode a `MACHINA_API_TOKEN` in their source code if using the MCP setup. The CLI handles shared context securely.
- **Pagination and Filtering Errors:** Public API docs often miss the `searchLimit` and nested `filters` required by the sports backend. Installing a template automatically injects the correct `workflow.json` config.
- **Lost Project Context:** Most premium commands silently fail without a default project. Always run `machina project use <id>` after a fresh login.
