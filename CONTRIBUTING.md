# Contributing to Machina Sports Skills

Thank you for your interest in contributing to the Machina Sports Skills repository! We welcome contributions from the community to help expand and improve our collection of AI agent skills for sports data.

## How to Create a New Skill

To create a new skill, follow these steps:

1.  **Create a New Directory**: Inside the `skills` directory, create a new directory for your skill. The directory name should be `kebab-case` and reflect the skill's purpose (e.g., `nba-player-stats`).
2.  **Create a `skill.yml` File**: Inside your new skill directory, create a `skill.yml` file. This manifest defines your skill's metadata and its entry points.
3.  **Develop Your Skill Logic**: Implement the core logic of your skill. This typically involves Python or TypeScript code that interacts with external APIs, processes data, or leverages Machina workflows/agents.
4.  **Define Workflows/Agents**: If your skill uses Machina workflows or agents, ensure they are properly defined and referenced in your `skill.yml`.

## Skill.yml Format

The `skill.yml` file is crucial for defining your skill. Here's an example of its structure:

```yaml
name: "nba-player-stats"
title: "NBA Player Statistics Skill"
description: "A skill to retrieve and analyze NBA player statistics."
version: "0.1.0"
workflows:
  - name: "get-player-career-stats"
  - name: "compare-player-stats"
agents:
  - name: "nba-data-analyst-agent"
```

**Required Fields:**

*   `name`: (string) A unique identifier for the skill (kebab-case).
*   `title`: (string) A human-readable title for the skill.
*   `description`: (string) A brief explanation of what the skill does.
*   `version`: (string) The version of the skill (e.g., "0.1.0").
*   `workflows`: (list of strings, optional) A list of Machina workflow names that this skill can execute.
*   `agents`: (list of strings, optional) A list of Machina agent names that this skill can execute.

## Testing

Before submitting your contribution, please ensure your skill is thoroughly tested.

*   **Local Testing**: You can test your skill locally using the `machina-cli`.
    *   Install your skill locally: `machina skills install ./path/to/your-skill`
    *   Run your skill: `machina skills run your-skill-name [key=value]`
*   **Unit Tests**: If your skill involves complex logic, consider adding unit tests using your preferred testing framework (e.g., `pytest` for Python).

## Submitting a PR

Once your skill is ready, follow these steps to submit a pull request:

1.  **Branch**: Create a new branch for your contribution:
    `git checkout -b feature/your-skill-name`
2.  **Commit**: Commit your changes with a clear and concise message:
    `git commit -m "feat: Add new NBA Player Stats skill"`
3.  **Push**: Push your branch to the remote repository:
    `git push origin feature/your-skill-name`
4.  **Open a Pull Request**: Go to the GitHub repository and open a new pull request from your branch to the `main` branch. Please provide a detailed description of your skill, its purpose, and how to test it.

We will review your PR as soon as possible. Thank you for your contribution!
