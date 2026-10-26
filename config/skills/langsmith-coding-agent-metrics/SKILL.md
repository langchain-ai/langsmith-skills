---
name: langsmith-coding-agent-metrics
description: "INVOKE THIS SKILL when asked how a coding agent traced to LangSmith (Claude Code, Codex, Cursor and similar) is being used: threads, turns, cost, thread length, pull requests opened or merged, and the costliest pull requests, overall or per user or harness. Uses the langsmith CLI tool."
---

<oneliner>
A coding agent in LangSmith is an Agent whose `agent_type` is `CODING`. Its sessions are traced to the Agent's production project. Each session is a **thread**, and each prompt in it is a **turn** (one trace). The GitHub outcome worker links traces to the pull requests they produced. This skill reads the numbers on the Agent's overview page with `langsmith api`: usage (threads, turns and cost), thread length, and pull request outcomes.
</oneliner>

<setup>
```bash
export LANGSMITH_API_KEY=<workspace-api-key>
export LANGSMITH_ENDPOINT=<your-langsmith-endpoint>   # only for self-hosted
langsmith --version
```

Requires [LangSmith CLI v0.2.57](https://github.com/langchain-ai/langsmith-cli/releases/tag/v0.2.57) or later: from that version, `langsmith api` retries rate-limited (429) responses with backoff. Install or update with `langsmith self-update`, or see the [CLI README](https://github.com/langchain-ai/langsmith-cli).

The examples build request bodies with `jq`. `langsmith api` sends a POST when given `--input`. An absolute path (`/api/...`) is used as-is. A non-2xx response prints its problem details, then a line `HTTP <status>`, and exits 1. That extra line breaks a `| jq` after the command, so rerun a failed call without `jq` to read its error.
</setup>

<cli_feedback>
After an actual CLI failure, undocumented workaround, confusing output, or missing capability, submit one concise product-feedback note per distinct issue in the task. Do not report routine successes, or metrics you merely found surprising.

**CLI requirement:** `langsmith feedback` requires [LangSmith CLI v0.2.58](https://github.com/langchain-ai/langsmith-cli/releases/tag/v0.2.58) or later. Check the installed version with `langsmith --version`.

Check `langsmith feedback --help` for `feedback <note>` and `--category`; if unavailable, skip feedback without raw HTTP or unreleased builds. Use the existing authenticated profile, endpoint, and workspace. Feedback goes to LangSmith Cloud, including through the BYOC relay; skip standalone self-hosted. Respect user/organization restrictions and ask first if permission to send feedback is unclear.

Summarize expected versus observed CLI behavior and any workaround in your own words. Never send secrets, customer data, trace payloads, prompts, full stack traces, copied command output, raw arguments, environment-variable values, local paths, or resource identifiers. The CLI adds version/OS/architecture, but does not redact your note; skip it if it cannot be safely redacted.

Choose `bug`, `feature-request`, `usability`, `documentation`, or `other`. This is CLI product feedback, not run evaluation feedback. Example shape only—do not submit unless actually encountered:

```bash
langsmith feedback --category feature-request --format json "There is no dedicated command for coding agent usage metrics, so raw API calls were needed."
```

Do not retry a failed or rate-limited feedback submission, switch credentials/endpoints to bypass a failure, or block the original task on feedback.
</cli_feedback>

<send_one_request_at_a_time>
**Never run these reads in parallel**: no `&`, `xargs -P` or concurrent tool calls. Thread stats for a project are served by a single query node with a bounded queue. A burst of reads overflows it, and every read then fails with `429 query queue is full`. The CLI retries a 429, but retries cannot drain a queue that you keep refilling. Run each command after the previous one returns, and read only the numbers the question needs.
</send_one_request_at_a_time>

<find_the_agent>
List the Agents and keep those with `agent_type` `CODING`. Use `name` to search by a case-insensitive partial name, and follow `next_cursor` to read the next page:

```bash
langsmith api "/api/v1/agents?page_size=100&name=claude" \
  | jq '.items[] | select(.agent_type == "CODING") | {id, name, environments}'
```

You need two values from the Agent you pick:
- `id`, the Agent ID used in the pull request paths. It is a slug such as `claude-code`, not a UUID.
- The `tracer_session_id` of the environment whose `environment` is `PRODUCTION`. This is the project the usage reads use. A coding agent traces only to production.

If several coding agents match, ask which one is meant. If none match, say so: the workspace may trace its coding agent to an ordinary project, which the `langsmith-trace` skill can read.
</find_the_agent>

<window>
Every read takes a window by trace start time, as ISO 8601 timestamps in UTC. Use the window the user names; otherwise use the last 7 days and say so. The pull request reads accept at most two weeks per call, starting within the run stats lookback (400 days on LangSmith Cloud). For a longer period, read consecutive windows of two weeks or less. Sum pull request counts across windows only when you say the sum may count a pull request twice: a pull request whose traces span two windows counts in both.

```bash
START=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```
</window>

<usage>
Threads, turns and cost for threads with a trace starting in the window:

```bash
jq -n --arg p "$PROJECT_ID" --arg s "$START" --arg e "$END" '{
  project_id: $p, min_start_time: $s, max_start_time: $e,
  select: ["THREAD_COUNT", "TRACE_COUNT", "TOTAL_COST"]
}' | langsmith api /api/v2/threads/stats --input -
# {"thread_count": 19, "trace_count": 189, "total_cost": 137.60}
```

`trace_count` is the number of turns, and `total_cost` is in USD. For averages, divide turns by threads or cost by threads yourself, and say how you derived them.

To narrow a read, add a `tree_filter` on root runs. Join clauses with `AND`, and quote values:

| Narrow to | `tree_filter` |
| --- | --- |
| One user | `is_root:true AND (metadata.ls_attribution_identifier:"jane@acme.com")` |
| One harness | `is_root:true AND (metadata.ls_integration:"claude-code")` |
| Traces linked to a merged PR | `is_root:true AND (feedback.ls_gh_attribution.score:2)` |
| ...a closed, unmerged PR | `is_root:true AND (feedback.ls_gh_attribution.score:1)` |
| ...an open PR | `is_root:true AND (feedback.ls_gh_attribution.score:0)` |
| Traces linked to no PR | `is_root:true AND (-feedback.ls_gh_attribution:*)` |

A filter selects **threads**, not turns. A filtered read counts the threads with any matching trace, and **all** of those threads' turns and cost in the window, including turns that do not match. Say so whenever you report a filtered figure: "turns in threads with a merged PR" is not "turns that produced a merged PR". Because a thread can match several values, per-value reads overlap, so never sum them into a total. A per-value breakdown takes one read per value, sent one after another. Find user values with the `group_by: user` pull request count below, or with the `langsmith-trace` skill. Do not guess values.
</usage>

<thread_length>
How many turns sessions take. Add a `thread_filter` on `turn_count`, one read per bucket, sent one after another. Keep to about five buckets:

| Bucket | `thread_filter` |
| --- | --- |
| 1 turn | `lt(turn_count, 2)` |
| 2–4 | `and(gte(turn_count, 2), lt(turn_count, 5))` |
| 5–9 | `and(gte(turn_count, 5), lt(turn_count, 10))` |
| 10–19 | `and(gte(turn_count, 10), lt(turn_count, 20))` |
| 20+ | `gte(turn_count, 20)` |

`turn_count` counts the thread's turns over its whole life, not only those in the window. Say so when the window is short.
</thread_length>

<pull_requests>
Distinct pull requests in each state that the window's traces are linked to:

```bash
jq -n --arg s "$START" --arg e "$END" '{start_time: $s, end_time: $e, filter: {}}' \
  | langsmith api "/api/v1/platform/coding-agents/$AGENT_ID/pull-request-counts" --input -
# {"total": {"merged": 12, "open": 3, "closed_unmerged": 2}, "groups": []}
```

- `filter` takes `outcomes` (`MERGED`, `CLOSED_UNMERGED`, `OPEN` or `UNATTRIBUTED`), `users` and `harnesses`. Each takes a list, matching any of its values.
- Add `"group_by": "user"` to also count each of the 20 users with the most traces, most first, in `groups[].value` and `groups[].counts`.
- A trace counts toward the best state of the pull requests it is linked to.

The costliest pull requests, ranked by the root-run cost of the traces linked to them:

```bash
jq -n --arg s "$START" --arg e "$END" '{start_time: $s, end_time: $e, limit: 5}' \
  | langsmith api "/api/v1/platform/coding-agents/$AGENT_ID/top-pull-requests" --input -
```

- Each item has `repository_full_name`, `pr_number`, `pr_url`, `state`, `cost_usd`, `trace_count` and `thread_count`.
- The repository fields are null when no outcome links the pull request to the Agent's projects.
- Narrow the ranking with `states`, `attribution_users` and `harnesses`. `limit` is 1–20.
- Only the 20 pull requests with the most traces are ranked. `candidates_limited: true` means more pull requests had traces, so call the list the costliest of the most active, not of all.

Both reads are experimental. They return **501** `GitHub thread outcomes are not enabled for this workspace` when the workspace does not have them. In that case report usage alone, and say that pull request metrics are not available for the workspace. If the reads succeed but every count is zero while usage is not, the Agent may have no GitHub connection: check the Agent's overview page in LangSmith. **400** means the window or filter is invalid: the detail says which.
</pull_requests>

<reporting>
- State the Agent, the window and every filter with the numbers.
- Quote numbers as returned; round cost to cents. Do not add counts from differently filtered reads, which overlap.
- Lead with the answer, such as "12 merged PRs from 189 turns ($137.60)", then a short label–value list for any breakdown.
- Link the pull requests with their `pr_url`.
</reporting>
