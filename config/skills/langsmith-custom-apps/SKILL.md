---
name: langsmith-custom-apps
description: "Deprecated: no longer maintained; see the LangSmith Custom Apps docs. INVOKE THIS SKILL when building, iterating on, copying, or sharing a LangSmith Custom App — a React/TypeScript UI that runs inside LangSmith and reads the LangSmith API. Covers the langsmith apps CLI, pulling an existing app's source, replicating an app into another workspace, verifying app logic without a browser, and sanitizing an app before sending it outside your org. Uses the langsmith CLI tool."
---

# langsmith-custom-apps has moved

This skill is no longer maintained. LangSmith skills now ship in the
`langchain-skills` plugin: https://github.com/langchain-ai/langchain-skills.

When this skill is invoked:

1. If the `langchain-agent-experiments` skill is available, use it to
   decide whether a Custom App fits, and build the app by following
   https://docs.langchain.com/langsmith/custom-apps.
2. Otherwise, tell the user once, briefly, that the LangSmith skills moved to
   `langchain-skills`, and offer to migrate by following
   https://github.com/langchain-ai/langchain-skills#migrate-from-the-standalone-skills.
   Do not install, update, or remove skills or plugins without the user's
   go-ahead.
3. Meanwhile, continue the user's task using the official docs
   (https://docs.langchain.com/llms.txt) and the current `langsmith --help`.
