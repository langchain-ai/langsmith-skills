---
name: langsmith-evaluator
description: "Deprecated: moved to the `langchain-agent-experiments` skill in langchain-ai/langchain-skills. INVOKE THIS SKILL when building evaluation pipelines for LangSmith. Covers three core components: (1) Creating Evaluators - LLM-as-Judge, custom code; (2) Defining Run Functions - how to capture outputs and trajectories from your agent; (3) Running Evaluations - locally with evaluate() or auto-run via LangSmith. Uses the langsmith CLI tool."
---

# langsmith-evaluator has moved

This skill is no longer maintained. LangSmith skills now ship in the
`langchain-skills` plugin: https://github.com/langchain-ai/langchain-skills.

When this skill is invoked:

1. If the `langchain-agent-experiments` skill is available in this session, use it
   instead and ignore the rest of this skill.
2. Otherwise, tell the user once, briefly, that the LangSmith skills moved to
   `langchain-skills`, and offer to migrate by following
   https://github.com/langchain-ai/langchain-skills#migrate-from-the-standalone-skills.
   Do not install, update, or remove skills or plugins without the user's
   go-ahead.
3. Meanwhile, continue the user's task using the official docs
   (https://docs.langchain.com/llms.txt) and the current `langsmith --help`.
