# Development Environment Setup

This guide will walk you through setting up a local development environment for Claude Worker. A proper setup ensures that your contributions adhere to the project's code style and quality standards.

## Step 1: Clone the Repository

If you haven't already, clone the repository to your local machine:

```bash
git clone https://github.com/yigitkonur/claude-worker.git
cd claude-worker
```

## Step 2: Install Dependencies

We use Poetry to manage all project dependencies. The `poetry install` command will create a dedicated virtual environment and install everything listed in `pyproject.toml`.

```bash
poetry install
```

## Step 3: Activate the Virtual Environment

To work on the project, you should always be inside the Poetry-managed virtual environment. Activate it with:

```bash
poetry shell
```

Your shell prompt should now indicate that you are in the `claude-worker` virtual environment. All subsequent commands in this guide assume you are in this shell.

## Step 4: Code Style and Linting

To maintain a consistent and high-quality codebase, we use `black` for code formatting and `ruff` for linting. While these are not listed as explicit dev dependencies in the `pyproject.toml`, they are standard tools for modern Python development and you should have them available.

You can install them into your active virtual environment:
```bash
pip install black ruff
```

### Running the Tools

Before you commit your changes or open a pull request, please run these tools to validate your code.

1.  **Format your code with `black`:**
    This will automatically reformat your files to match the project's style.
    ```bash
    black src/
    ```

2.  **Lint your code with `ruff`:**
    This will check for common errors, style guide violations, and potential bugs.
    ```bash
    ruff check src/
    ```

Running these checks locally before submitting a PR helps streamline the review process and ensures your code can be merged more quickly.

## Step 5: Running in Development Mode

To test your changes to the server, you can run it with the `--reload` flag. This will automatically restart the server whenever you save a file.

```bash
claude-worker server start --reload
```

You are now fully equipped to start contributing to Claude Worker!