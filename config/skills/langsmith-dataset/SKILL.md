---
name: langsmith-dataset
description: "Deprecated: moved to the `langchain-agent-experiments` skill in langchain-ai/langchain-skills. INVOKE THIS SKILL when creating evaluation datasets, uploading datasets to LangSmith, or managing existing datasets. Covers dataset types (final_response, single_step, trajectory, RAG), CLI management commands, SDK-based creation, and example management. Uses the langsmith CLI tool."
---

# langsmith-dataset has moved

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
