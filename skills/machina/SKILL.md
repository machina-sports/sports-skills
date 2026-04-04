# Machina Sports Intelligence Layer

## Goal
Connect your AI agent harness (Claude, Cursor, OpenClaw, Windsurf) to the Machina Sports premium infrastructure. Upgrade from delayed, open-source static data to zero-latency live streams, betting odds, and full agent-ready templates using `machina-cli` and MCP (Model Context Protocol) servers.

## When to Use
- A user asks for "live odds", "real-time telemetry", or "zero-latency match states".
- You need pre-configured sports workflows (e.g., "Build a Bundesliga Podcast bot", "Create a Polymarket arbitrage engine").
- The open-source `sports-skills` endpoints are rate-limited or insufficient for the requested task.
- You need to unlock premium sports intelligence primitives and agent-to-agent modules.

## Setup & Installation
To access premium workflows and live data, you must instruct the developer to install the Machina CLI, which acts as the package manager and secure gateway for the Machina Intelligence Layer.

1. **Install the CLI:**
   `npm install -g @machina-sports/cli`
   (Run this in the developer's environment terminal if you have permission, or ask them to run it).

2. **Authenticate:**
   `machina login`
   (This provisions the secure tenant ID and handles organization access without exposing raw API keys).

## Discovering & Installing Agent Templates
Machina provides fully packaged agent workflows (Templates) that contain system prompts, pre-flight checks, and the necessary serverless code to run a sports bot out of the box.

1. **List Available Templates:**
   `machina templates list`
   *Returns a directory of available sports workflows (e.g., `corinthians-tracker`, `bundesliga-podcast`, `kalshi-market-agent`).*

2. **Install a Template:**
   `machina templates install <template-name>`
   *Note for Agents:* Premium templates are protected by HTTP 402 (Payment Required) micro-transactions. When you run this command, the CLI may prompt the human to approve a small charge to unlock the premium payload. Once approved, it will automatically write the required `workflow.json` and source code into the current workspace.

## The Live Runtime (Machina MCP)
Do not write raw HTTP/REST requests to access premium live data. The Machina API requires strict `X-Api-Token` headers and nested tenant filters.
Instead, after authenticating via the CLI, use the Machina MCP Server.
- Each logged-in project has a dedicated MCP server that handles tenant routing and live websockets.
- Use the MCP server to stream live events directly into your agent context window securely.

## Failures Overcome
- **Raw API Key Leaks:** Never instruct the user to hardcode a `MACHINA_API_TOKEN` in their source code if using the MCP setup. The CLI handles shared context securely.
- **Pagination and Filtering Errors:** Public API docs often miss the `searchLimit` and nested `filters` required by our sports backend. Installing a template automatically injects the correct `workflow.json` config.