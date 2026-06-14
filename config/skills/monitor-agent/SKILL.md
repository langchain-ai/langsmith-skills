---
name: monitor-agent
description: "INVOKE when the user runs /monitor-agent, or wants production monitoring / online evals / alerts / dashboards for an agent. The Monitor phase of the ADLC — works standalone or as a step of /productionalize-agent. Gated on TRACING (not cloud deploy). Uses langsmith-trace + langsmith-evaluator."
version: 1.0.0
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion, WebFetch]
triggers: ["monitor my agent", "online evals", "set up alerts", "production dashboard"]
---

<oneliner>
Watch the agent on live traffic: online evaluators on a sample of traces, dashboards, and alerts.
</oneliner>

<entry>
Standalone drop-in — the prime "harden an in-prod agent" entry point. On entry:
1. Load `.adlc.json`; if absent, bootstrap by inspecting the agent + traces; mark earlier phases done.
2. **Prereq: tracing is live** (NOT a cloud deploy — dev/test/red-team runs count). If traces exist you're already monitoring; surface the project dashboard immediately. If trusted evals exist, offer to promote them online; if not, offer a quick `/test-agent` to define dimensions, or just wire dashboards/alerts.
3. Follow the SHARED conventions in `../productionalize-agent/SKILL.md`. Teaching: `../productionalize-agent/scripts/teach.py --print monitor`.
</entry>

<prereqs>
A traced agent (a LangSmith project with runs). Online evals need at least one eval dimension (reuse Test's, or define here).
</prereqs>

<flow>
**Iron Law — monitoring needs traces, not a cloud deploy.** If traces flow, you're already monitoring; start there.

**Monitor is gated on TRACING (live since Build), NOT a cloud deploy** — dev/test/red-team runs already populate the dashboards.
- **Surface the live dashboard URL** first (it's populated the moment traces flow).
- **monitoring?** If yes: ask **which checks to run online** (multiselect over the project's judges — groundedness/scope/tool-safety…) and a **sampling rate** (% of live traces; online evals cost a judge call per sampled run, so 100% is rarely worth it). Create **online evaluators** (run-rules) on the project at that rate. Surface the cost/coverage tradeoff.
- **ci_watches?** (multi) cost · quality · safety.
- **alerts?** Ask which signals — errors/failures · latency spikes · feedback-score drops · cost-per-trace spikes — and whether to set up now (LangSmith **alerts UI** — point them there; UI-configured, not scripted), skip, or **defer → `pending_reminders`**. Alerts can notify via **Slack / email / PagerDuty / webhook** — see [LangSmith alerts](https://docs.langchain.com/langsmith/alerts) for channel setup.
- **hitl?** route flagged/generated examples through an **annotation queue** for human review (edit input/output, write/adjust assertions, Add to Dataset). Use for curating red-team examples and triaging production thumbs-downs. Queues are ADD-feedback, not edit-existing.
</flow>
