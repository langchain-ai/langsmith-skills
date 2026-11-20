---
name: langsmith-experiment-diagnosis
description: "Deprecated: moved to the `langchain-agent-experiments` skill in langchain-ai/langchain-skills. Investigate a LangSmith experiment with the LangSmith CLI, identify examples with poor evaluator results, explain likely causes using run evidence, and propose targeted fixes. Use when a user asks why an experiment performed badly or which evaluated examples need attention."
---

# langsmith-experiment-diagnosis has moved

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
