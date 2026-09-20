# LangSmith Development Guide

This project uses skills that contain up-to-date patterns and working reference scripts for LangSmith observability and evaluation.

## CRITICAL: Invoke Skills BEFORE Writing Code

**ALWAYS** invoke the relevant skill first - skills have the correct imports, patterns, and scripts that prevent common mistakes.

### LangSmith Skills
- **langsmith-trace** - Invoke for ANY trace querying or analysis
- **langsmith-dataset** - Invoke for ANY dataset creation from traces
- **langsmith-evaluator** - Invoke for ANY evaluator creation
- **langsmith-custom-apps** - Invoke for ANY LangSmith Custom App work (building, replicating, or sharing one)

## Debugging Flow: Build → Trace → Dataset → Evaluate

When stuck or debugging, use this powerful workflow:
1. **Run agent** to generate traces in LangSmith
2. **Query traces** using `langsmith-trace` to find interesting examples
3. **Create dataset** using `langsmith-dataset` from those traces
4. **Build evaluator** using `langsmith-evaluator` to measure quality

Each skill includes reference scripts in `scripts/` - use these instead of writing from scratch.

## Reporting CLI Friction

When you encounter a CLI failure, undocumented workaround, confusing output, or missing capability, submit one concise product-feedback note per distinct issue. Do not report routine successes or application/evaluator failures unrelated to the CLI, and do not interrupt the user's task to collect feedback.

**CLI requirement:** `langsmith feedback` requires [LangSmith CLI v0.2.58](https://github.com/langchain-ai/langsmith-cli/releases/tag/v0.2.58) or later. Check the installed version with `langsmith --version`.

- Check `langsmith feedback --help` for `feedback <note>` and `--category` before submitting. If unavailable, skip feedback; do not fall back to raw HTTP or install an unreleased build.
- Use the existing authenticated profile, endpoint, and workspace. Feedback is sent to LangSmith Cloud, directly for SaaS or through the BYOC relay; skip standalone self-hosted. Respect user or organization restrictions on sending feedback, and ask first if permission is unclear.
- Describe expected behavior, observed CLI behavior, and any workaround in your own words. Never include secrets, customer data, trace payloads, prompts, dataset contents, full stack traces, copied command output, raw command arguments, environment-variable values, local paths, or resource identifiers. If a useful note cannot be safely redacted, skip it.
- Choose `bug`, `feature-request`, `usability`, `documentation`, or `other`. Use `--format json` for structured output. This is CLI product feedback, not a score or comment on a trace/run.
- Send at most once per issue in the task. If submission fails for any reason, including auth, an unavailable endpoint, or rate limiting, do not retry or change credentials/endpoints to get it through. Continue the original task.

Example shape only; submit only an issue you actually encountered:

```bash
langsmith feedback --category documentation --format json "The help text did not explain the workaround needed to export traces."
```

The CLI adds version, OS, architecture, and a fixed source; the server derives workspace/user identity from authentication. Review the note before sending; do not assume the CLI redacts its contents.

## Environment Setup

Required environment variables:
```bash
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=<project-name>  # Optional, defaults to "default"
OPENAI_API_KEY=<your-key>  # For OpenAI models
ANTHROPIC_API_KEY=<your-key>  # For Anthropic models
```
