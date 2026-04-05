# Machina Sports Intelligence Layer

## Goal
Connect your AI agent harness (Claude, Cursor, OpenClaw, Windsurf) to the Machina Sports premium infrastructure. Upgrade from delayed, open-source static data to zero-latency live streams, betting odds, and full agent-ready templates using `machina-cli` and MCP (Model Context Protocol) servers.

## When to Use
- The developer needs to build an agent/workflow that runs 24/7 in the cloud (not just locally).
- The developer needs a premium connector (e.g. from `machina-templates/connectors`) or requires licensed data that relies on official API keys (Sportradar, etc).
- The developer wants to install or deploy a pre-configured template (e.g. "Build a Bundesliga Podcast bot").
- You need zero-latency live streams or real-time betting odds.
*(Note: For basic open-source free data running locally on the developer's laptop, continue using the standard `sports-skills` files normally).*
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

## Building Custom Workflows (The Agent IDE)
If the developer asks you to build a new template or custom workflow from scratch, **DO NOT** guess the Machina YAML syntax or attempt to write random code. You must first install the Machina Constructor Skill to get the official schema references:

1. **Install the Constructor:**
   `machina templates install skills/mkn-constructor --json`
2. **Read the Docs:**
   Read the `./mkn-constructor/SKILL.md` file immediately. It acts as your local "Agent IDE" and contains complete schema definitions, intent routing, validation guides, and the correct YAML syntax to scaffold Machina templates flawlessly.

## Pushing Custom Agent Workflows
If you modify a template or create a new sports workflow locally, you can deploy it directly to the Machina Cloud Pod.
1. **Push to Cloud:**
   `machina templates push ./<your-custom-folder>`
   *This zips your local workspace, uploads it to the backend, and automatically provisions the new webhook endpoints and data streams for live use.*

## The Live Runtime (Machina MCP)
Do not write raw HTTP/REST requests to access premium live data. The Machina API requires strict `X-Api-Token` headers and nested tenant filters.
Instead, after authenticating via the CLI, use the Machina MCP Server.
- Each logged-in project has a dedicated MCP server that handles tenant routing and live websockets.
- Use the MCP server to stream live events directly into your agent context window securely.

## Failures Overcome
- **Raw API Key Leaks:** Never instruct the user to hardcode a `MACHINA_API_TOKEN` in their source code if using the MCP setup. The CLI handles shared context securely.
- **Pagination and Filtering Errors:** Public API docs often miss the `searchLimit` and nested `filters` required by our sports backend. Installing a template automatically injects the correct `workflow.json` config.