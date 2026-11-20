# LangSmith Skills

> [!IMPORTANT]
> **This repository is deprecated and will be archived.** The LangSmith skills
> moved to [langchain-ai/langchain-skills](https://github.com/langchain-ai/langchain-skills),
> which ships them with the LangChain, LangGraph, and Deep Agents skills in one
> plugin, together with the LangChain docs and API reference MCP servers. This
> repository no longer receives updates; its skills now only point to their
> replacements.

## Migrate

Remove these skills first, so your agent doesn't see two overlapping sets of
guidance, then install the new plugin. The full steps for every install method
are in the
[langchain-skills migration guide](https://github.com/langchain-ai/langchain-skills#migrate-from-the-standalone-skills).

- **Claude Code plugin:** remove this marketplace, which also uninstalls its
  plugin, then install the new one and turn on
  [auto-update](https://github.com/langchain-ai/langchain-skills#updates):

  ```bash
  claude plugin marketplace remove langsmith-skills
  claude plugin install langchain-skills --marketplace langchain-ai/langchain-skills
  ```

- **`npx skills`:** remove the old skills (once with `--global`, and once in
  each project where you installed them), then add the new ones:

  ```bash
  npx skills remove langsmith-custom-apps langsmith-dataset langsmith-evaluator \
    langsmith-experiment-diagnosis langsmith-graph-evaluator \
    langsmith-online-eval-engineering langsmith-trace --global --yes
  npx skills add langchain-ai/langchain-skills --skill '*' --yes --global
  ```

- **`install.sh` or a copy:** delete the `langsmith-*` skill folders from the
  skills directory you installed into, such as `~/.claude/skills/` or
  `.claude/skills/`, then install the new plugin.
- **Deep Agents Code:** install from the new marketplace:

  ```bash
  dcode plugin marketplace add langchain-ai/langchain-skills
  dcode plugin install langchain-skills@langchain-skills
  ```

Or paste this into your coding agent:

> Migrate me to the langchain-skills plugin by following
> https://github.com/langchain-ai/langchain-skills#migrate-from-the-standalone-skills:
> remove the old standalone skills, install the plugin, and enable auto-update
> for its marketplace.

## Where each skill went

| Old skill | New skill |
|------|-------------|
| `langsmith-trace` | `langchain-agent-tracing` |
| `langsmith-online-eval-engineering` | `langchain-agent-monitoring` |
| `langsmith-dataset`, `langsmith-evaluator`, `langsmith-graph-evaluator`, `langsmith-experiment-diagnosis` | `langchain-agent-experiments` |
| `langsmith-custom-apps` | Removed as a skill. `langchain-agent-experiments` covers when to use a Custom App; to build one, see the [Custom Apps docs](https://docs.langchain.com/langsmith/custom-apps). |

The last full version of these skills is in this repository's git history.
Contribute to [langchain-skills](https://github.com/langchain-ai/langchain-skills)
instead of opening pull requests here.
