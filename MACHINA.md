# Machina Platform Integration

This repository integrates with the Machina Platform, providing a robust environment for developing and deploying AI agents and workflows. The Machina platform offers tools for authentication, organization and project management, workflow and agent execution, and skill development.

## machina-cli Commands

The `machina-cli` is the primary command-line interface for interacting with the Machina platform. Below are some essential commands:

### Authentication
- `machina login`: Browser-based Clerk SSO login.
- `machina login --api-key <key>`: Login using an API key (suitable for CI/CD).
- `machina login --with-credentials`: Login using username and password.
- `machina auth whoami`: Display the current authenticated user.
- `machina auth logout`: Clear local credentials.

### Organizations & Projects
- `machina org list`: List all organizations the user belongs to.
- `machina org use <org-id>`: Set a default organization for subsequent commands.
- `machina org create <name>`: Create a new organization.
- `machina project list`: List projects within the default organization.
- `machina project use <project-id>`: Set a default project for subsequent commands.
- `machina project create <name>`: Create a new project.
- `machina project status`: Check the deployment status of the current project's Client API.

### Workflows
- `machina workflow list`: List all workflows available in the default project.
- `machina workflow get <name>`: Get details and required inputs for a specific workflow.
- `machina workflow run <name>`: Run a workflow interactively, prompting for inputs.
- `machina workflow run <name> key=value`: Run a workflow with inline parameters (synchronous execution).
- `machina workflow run <name> --async --watch`: Run a workflow asynchronously and poll for its completion.

### Agents
- `machina agent list`: List all agents available in the default project.
- `machina agent get <name>`: Get details about an agent, including its workflows, context variables, and activity.
- `machina agent run <name>`: Run an agent asynchronously (default behavior).
- `machina agent run <name> --sync`: Run an agent synchronously and wait for the result.
- `machina agent run <name> --watch`: Run an agent and poll for its completion every 3 seconds (with a 300s timeout).
- `machina agent run <name> key=value`: Run an agent while passing context variables.

### Executions
- `machina execution list`: List recent workflow and agent executions.
- `machina execution get <id>`: Get detailed information about a specific execution (status, tokens, workflows involved, response).
- `machina execution get <id> --compact`: Get a summary of an execution without the full response.

### Skills (installable agent capabilities)
- `machina skills list`: Browse the Machina Skills registry (machina-templates repository).
- `machina skills install <path>`: Install a skill (provisions cloud resources and downloads local files).
- `machina skills info <path>`: Read the local `skill.yml` manifest for a skill.
- `machina skills run <name> [key=value]`: Resolve the skill entrypoint and run the associated workflow or agent.
- `machina skills push <dir>`: Upload a local skill package to the platform.
- `machina skills constructor`: Bootstrap the `mkn-constructor` authoring bridge.

### Templates (full project starters)
- `machina template list`: Browse the Machina Template repository.
- `machina template install <path>`: Install a template (provisions cloud resources and downloads project files).
- `machina template push <dir>`: Upload a custom template (requires an `_install.yml` manifest).

### Connectors, Mappings, Prompts & Documents
- `machina connector list / get <name>`: Manage data source integrations.
- `machina mapping list / get <name>`: Manage data transformation rules.
- `machina prompt list / get <name>`: Manage LLM prompt templates (includes model information).
- `machina document list / get <id>`: Manage knowledge base documents.

### Credentials
- `machina credentials generate`: Generate a new API key (default: SERVICE_ACCESS level).
- `machina credentials generate --name my-key`: Generate a named API key.
- `machina credentials list [--show-keys]`: List API keys (masked by default).
- `machina credentials list --copy client-api`: Copy a client-api key to the clipboard.
- `machina credentials revoke <key-id>`: Revoke an API key.

### Deployment
- `machina deploy start [--version beta]`: Deploy the Client API for the current project.
- `machina deploy status`: Check the deployment status.
- `machina deploy restart`: Restart an existing deployment.

### Configuration
- `machina config list`: Display all current `machina-cli` configuration settings.
- `machina config set api_url https://api.machina.gg`: Set the Machina Core API URL.
- `machina config set default_organization_id <org-id>`: Set the default organization ID.
- `machina config set default_project_id <project-id>`: Set the default project ID.

### Global Options
- `--limit N` / `-l N`: Set the number of items per page for list commands (default: 20).
- `--page N`: Specify the page number for list commands.
- `--json` / `-j`: Output raw JSON.
- `--project ID` / `-p ID`: Override the default project ID for a command.