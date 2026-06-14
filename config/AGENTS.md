# LangSmith Development Guide

This project uses skills that contain up-to-date patterns and working reference scripts for LangSmith observability and evaluation.

## CRITICAL: Invoke Skills BEFORE Writing Code

**ALWAYS** invoke the relevant skill first - skills have the correct imports, patterns, and scripts that prevent common mistakes.

### LangSmith Skills
- **langsmith-trace** - Invoke for ANY trace querying or analysis
- **langsmith-dataset** - Invoke for ANY dataset creation from traces
- **langsmith-evaluator** - Invoke for ANY evaluator creation

### ADLC Skills (idea → production)
A guided suite that takes an agent through the **Agent Development Life Cycle** (Scope → Build → Test → Deploy → Monitor → Improve). Each phase is a standalone drop-in command; the orchestrator runs them in order. They build on the three skills above.
- **productionalize-agent** - The ORCHESTRATOR. Invoke for the full guided journey from idea to a deployed, monitored agent. Owns shared state (`.adlc.json`) + conventions.
- **build-agent** - Scope + Build: scaffold a new agent (or instrument an existing one) until traces flow to LangSmith.
- **test-agent** - Test: build a dataset + evaluators you trust (align them), then red→green the agent. TDD for agents.
- **deploy-agent** - Deploy: a thin deployment-client frontend + auth, shipped to LangSmith Deployment or your own infra.
- **monitor-agent** - Monitor: online evaluators on sampled traffic + dashboards + alerts.
- **improve-agent** - Improve: failing-trace + 👎-feedback → annotation queue → dataset → CI loop.

## Debugging Flow: Build → Trace → Dataset → Evaluate

When stuck or debugging, use this powerful workflow:
1. **Run agent** to generate traces in LangSmith
2. **Query traces** using `langsmith-trace` to find interesting examples
3. **Create dataset** using `langsmith-dataset` from those traces
4. **Build evaluator** using `langsmith-evaluator` to measure quality

Each skill includes reference scripts in `scripts/` - use these instead of writing from scratch.

## Environment Setup

Required environment variables:
```bash
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=<project-name>  # Optional, defaults to "default"
OPENAI_API_KEY=<your-key>  # For OpenAI models
ANTHROPIC_API_KEY=<your-key>  # For Anthropic models
```
