# Contribution Guide

Thank you for your interest in contributing to Claude Worker! We welcome contributions of all kinds, from bug reports and documentation improvements to new features. This guide will help you get started.

## How to Contribute

We use the standard GitHub "fork and pull request" workflow.

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine:
    ```bash
    git clone https://github.com/YOUR_USERNAME/claude-worker.git
    cd claude-worker
    ```
3.  **Create a new branch** for your changes. Please choose a descriptive name.
    ```bash
    git checkout -b feature/add-new-cli-command
    ```
4.  **Make your changes.** Follow the project's coding style and philosophy. See our [Development Setup](./06-contributing-development-setup.md) guide for more details.
5.  **Commit your changes** with a clear and concise commit message.
    ```bash
    git commit -m "feat: Add 'claude-worker logs' command"
    ```
6.  **Push your branch** to your fork on GitHub.
    ```bash
    git push origin feature/add-new-cli-command
    ```
7.  **Open a Pull Request (PR)** from your branch to the `main` branch of the original `yigitkonur/claude-worker` repository.
8.  **Provide a clear description** of your PR, explaining the "what" and "why" of your changes. If it resolves an existing issue, please reference it (e.g., `Fixes #123`).

## Where Help Is Needed: The Roadmap

Not sure where to start? Our official **[Project Roadmap](./ROADMAP.md)** is the best place to find high-impact areas where your help is most needed.

The roadmap lists planned features, bug fixes, and quality-of-life improvements that are priorities for the project. Tackling an item from the roadmap is a fantastic way to make a meaningful contribution. Some key areas where we are actively seeking help include:

*   **Adding a comprehensive test suite:** The project currently lacks automated tests. This is the single most valuable area for contribution.
*   **Implementing native API authentication:** Improving the security of the server is a top priority.
*   **Making more settings configurable:** Reducing the number of hardcoded values for better production deployment.
*   **Improving the CLI:** Adding new commands or improving the output of existing ones.

## Reporting Bugs and Suggesting Features

If you find a bug or have an idea for a new feature, please open an issue on the [GitHub Issues](https://github.com/yigitkonur/claude-worker/issues) page.

When reporting a bug, please include:
*   Your operating system and Python version.
*   Steps to reproduce the bug.
*   The full error message and traceback, if any.
*   The expected behavior vs. the actual behavior.

We look forward to your contributions!