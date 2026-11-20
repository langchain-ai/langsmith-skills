---
name: langsmith-graph-evaluator
description: "Deprecated: moved to the `langchain-agent-experiments` skill in langchain-ai/langchain-skills. Experimental. Build a LangSmith evaluator as a graph of steps with openevals.graph: code checks, LLM judges, and decision models wired together, traced as a single evaluator trace and drawn as a graph in LangSmith. Use when an evaluator needs several chained checks or the user asks for a graph or multi-step evaluator. For a single judge or code check, use langsmith-evaluator."
---

# langsmith-graph-evaluator has moved

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
