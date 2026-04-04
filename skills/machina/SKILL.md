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
   Via bash: `curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh | bash`
   Via Python: `pip install machina-cli`
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
   *Note for Agents:* Running this command will automatically write the required `workflow.json` and source code into the current workspace.

## Deploying Custom Agent Workflows
If you modify a template or create a new sports workflow locally, you can deploy it directly to the Machina Cloud Pod.
1. **Deploy to Cloud:**
   `machina templates deploy ./<your-custom-folder>`
   *This zips your local workspace, uploads it to the backend, and automatically provisions the new webhook endpoints and data streams for live use.*

## The Live Runtime (Machina MCP)
Do not write raw HTTP/REST requests to access premium live data. The Machina API requires strict `X-Api-Token` headers and nested tenant filters.
Instead, after authenticating via the CLI, use the Machina MCP Server.
- Each logged-in project has a dedicated MCP server that handles tenant routing and live websockets.
- Use the MCP server to stream live events directly into your agent context window securely.

## Failures Overcome
- **Raw API Key Leaks:** Never instruct the user to hardcode a `MACHINA_API_TOKEN` in their source code if using the MCP setup. The CLI handles shared context securely.
- **Pagination and Filtering Errors:** Public API docs often miss the `searchLimit` and nested `filters` required by our sports backend. Installing a template automatically injects the correct `workflow.json` config.