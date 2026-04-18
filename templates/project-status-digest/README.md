# Project Status Digest Template

This Machina template fetches recent activity using the `sports-news` connector and passes the results to a Google Gemini agent to compose a short, friendly digest (3-5 bullets).

## Features
- Connects to the existing `sports-news` connector for recent activity.
- Leverages the `google-genai` connector to format the output cleanly.
- Outputs a concise 3-5 bullet point digest.

## Installation & Deployment

1. **Install the template:**
   Use the Machina CLI to install this template into your workspace.
   ```bash
   machina template install templates/project-status-digest
   ```

2. **Push to Cloud:**
   Upload the custom template to the Machina Cloud Pod:
   ```bash
   machina template push templates/project-status-digest
   ```
   *This validates the `_install.yml` manifest and provisions the workflows and agent prompts.*

## Context Variables

This template requires the following context variables to be set in your Machina project for the AI generation step:

- `GEMINI_API_KEY`: The API key for Google Gemini (Vertex AI) if required by the cloud environment.

Set context variables via the CLI:
```bash
machina config set GEMINI_API_KEY <your-key>
```
Or pass them when running the workflow:
```bash
machina workflow run project-status-digest-workflow query="NFL Draft" GEMINI_API_KEY="<your-key>"
```

## Usage

Run the workflow interactively:
```bash
machina workflow run project-status-digest-workflow
```

Or run synchronously with parameters:
```bash
machina workflow run project-status-digest-workflow query="Arsenal transfer"
```
