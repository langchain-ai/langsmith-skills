# LangSmith Skills

> **⚠️** — This project is in early development. APIs and skill content may change.

Agent skills for observing and evaluating LLM applications with [LangSmith](https://smith.langchain.com/). Query traces, build evaluation datasets, and create custom evaluators — all from your coding agent.

## Supported Coding Agents

These skills can be installed for the following AI coding agents:

| Agent | Local Install | Global Install |
|-------|---------------|----------------|
| **Claude Code** | `.claude/skills/` | `~/.claude/skills/` |
| **DeepAgents CLI** | `.deepagents/skills/` | `~/.deepagents/langchain_agent/skills/` |

**Note:** The `config/AGENTS.md` file is primarily for reference and is **not copied** during installation (except for DeepAgents global installs where it defines the agent persona). It may be a helpful example to incorporate into your existing `CLAUDE.md` or `AGENTS.md` configuration.

## Prerequisites

- [Claude Code](https://claude.ai/claude-code) or [DeepAgents CLI](https://github.com/anthropics/deepagents-cli) installed
- A [LangSmith API key](https://smith.langchain.com/)

## Installation

### Quick Install (Local)

Install into the current directory with a single command (run from your project root):

**Claude Code:**
```bash
curl -fsSL https://github.com/langchain-ai/langsmith-skills/archive/main.tar.gz | tar -xz -C /tmp && /tmp/langsmith-skills-main/install.sh -y && rm -rf /tmp/langsmith-skills-main
```

**DeepAgents CLI:**
```bash
curl -fsSL https://github.com/langchain-ai/langsmith-skills/archive/main.tar.gz | tar -xz -C /tmp && /tmp/langsmith-skills-main/install.sh --deepagents -y && rm -rf /tmp/langsmith-skills-main
```

### Quick Install (Global)

Install globally with a single command:

**Claude Code:**
```bash
curl -fsSL https://github.com/langchain-ai/langsmith-skills/archive/main.tar.gz | tar -xz -C /tmp && /tmp/langsmith-skills-main/install.sh --global -y && rm -rf /tmp/langsmith-skills-main
```

**DeepAgents CLI:**
```bash
curl -fsSL https://github.com/langchain-ai/langsmith-skills/archive/main.tar.gz | tar -xz -C /tmp && /tmp/langsmith-skills-main/install.sh --deepagents --global -y && rm -rf /tmp/langsmith-skills-main
```

### Using `npx skills`

```bash
npx skills add /path/to/langsmith-skills --yes
```

### Manual Install

Clone the repo and run the install script for more options:

```bash
# Install for Claude Code in current directory (default)
./install.sh

# Install for Claude Code globally
./install.sh --global

# Install for DeepAgents CLI in current directory
./install.sh --deepagents

# Install for DeepAgents CLI globally (includes agent persona)
./install.sh --deepagents --global

# Force reinstall without prompts
./install.sh -f -y
```

### Options

| Flag | Description |
|------|-------------|
| `--claude` | Install for Claude Code (default) |
| `--deepagents` | Install for DeepAgents CLI |
| `--global`, `-g` | Install globally instead of current directory |
| `--force`, `-f` | Overwrite skills with same names as this package |
| `--yes`, `-y` | Skip confirmation prompts |

## Usage

After installation, set your API keys:

```bash
export LANGSMITH_API_KEY=<your-key>
export OPENAI_API_KEY=<your-key>      # For OpenAI models
export ANTHROPIC_API_KEY=<your-key>   # For Anthropic models
```

Then run your coding agent from the directory where you installed (for local installs) or from anywhere (for global installs).

## Available Skills (3)

### LangSmith
- **langsmith-trace** - Query and export traces (includes helper scripts)
- **langsmith-dataset** - Generate evaluation datasets from traces (includes helper scripts)
- **langsmith-evaluator** - Create custom evaluators (includes helper scripts)

**Note:** All skills include Python and TypeScript helper scripts for common operations.

## Development

Agent configuration lives in `config/`. To update an existing installation:

```bash
./install.sh --force
```
