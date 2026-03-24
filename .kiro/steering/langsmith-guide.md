---
inclusion: auto
name: langsmith-guide
description: LangSmith development guide for tracing, datasets, and evaluation workflows. Use when working with LangSmith observability or evaluation pipelines.
---

# LangSmith Development Guide

This project uses LangSmith for observability and evaluation of LLM applications.

## CRITICAL: Check Skills BEFORE Writing Code

ALWAYS check the relevant skill first — skills have the correct imports, patterns, and CLI commands that prevent common mistakes.

### Available LangSmith Skills (activate via `#` in chat)
- **langsmith-trace** — Query and export traces
- **langsmith-dataset** — Generate evaluation datasets from traces
- **langsmith-evaluator** — Create custom evaluators

## Debugging Flow: Build → Trace → Dataset → Evaluate

When stuck or debugging, use this workflow:
1. Run agent to generate traces in LangSmith
2. Query traces using `langsmith-trace` skill to find interesting examples
3. Create dataset using `langsmith-dataset` skill from those traces
4. Build evaluator using `langsmith-evaluator` skill to measure quality

## Environment Setup

Required environment variables:
```bash
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=<project-name>  # Optional, defaults to "default"
OPENAI_API_KEY=<your-key>         # For OpenAI models
ANTHROPIC_API_KEY=<your-key>      # For Anthropic models
```

## CLI Tool

All skills use the `langsmith` CLI. Install with:
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```
