# Harbor evals — handoff

Regression harness for the skills in `config/skills/`. Harbor is the only eval mechanism
here — no pytest anywhere, by design.

Run results, cost and latency figures, and skill-comparison analysis are deliberately kept
out of this repo. They live in `evals/notes/` (gitignored) alongside the raw evidence in
`evals/jobs/` (also gitignored).

## What exists

```
evals/
  run.py              orchestrator: project per trial -> harbor run -> reward -> cleanup
  langsmith_env.py    project/dataset naming, suffix-scoped cleanup, orphan sweep
  pyproject.toml      pins harbor[langsmith]==0.18.0, isolated from the global install
  trace-instrument/   instrument two untraced apps and report each trace id
  offline-eval-setup/ set up offline regression evaluation for an app
.github/workflows/evals.yml   workflow_dispatch only
```

`trace-instrument` ships two untraced apps and asks the agent to trace both into
`$LANGSMITH_PROJECT`, then report each trace id:

- `chain_app/` — LangChain. Correct fix is env vars only, no code change.
- `plain_app/` — raw OpenAI SDK. Correct fix is `wrap_openai` + `@traceable` on each
  nested function.

`offline-eval-setup` poses one realistic request — *"we're changing this app and have no
regression checks; set us up"* — and spans `langsmith-dataset` + `langsmith-evaluator`.
Test cases ship as a file, so no LangSmith state is seeded and no setup hook is needed. Its
app is a deterministic LangChain Runnable with **no LLM**: no model deprecations, no gateway
dependency, no per-case cost, and known-exact outputs. The fixture is shaped so the app
answers two of three cases per their references and gets the third wrong, so any sensible
metric must rank that case lowest — the verifier asserts that ordering and never a metric,
evaluator name, or mechanism.

Both verifiers score from live LangSmith state only — no source regex, since an import that
survives a commented-out call would satisfy a regex while producing no trace at all. Each
`task.toml` carries its own pass rule, fairness reasoning, and reward-hack analysis in its
`[metadata]` comments.

## Running it

```bash
uv run --project evals python evals/run.py                        # normal run
uv run --project evals python evals/run.py --task offline-eval-setup
uv run --project evals python evals/run.py --langsmith-experiment # + experiment, keeps traces
uv run --project evals python evals/run.py --no-skills            # control, informational
uv run --project evals python evals/run.py --agent oracle -m none # verifier calibration, $0
uv run --project evals python evals/run.py --cleanup-only <run_id>
```

Exit codes: 0 clean · 1 reward regression · 2 skill never invoked · 3 infra · 4 usage.

Needs `evals/.env` (gitignored) with `LANGSMITH_API_KEY` plus the gateway vars
(`ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL` → `gateway.smith.langchain.com`, both keys set to
the LangSmith key).

## Learnings worth keeping

- **Write the oracle before anything else.** `--agent oracle -m none` runs
  `solution/solve.sh` and calibrates the verifier for $0. It has repeatedly caught verifier
  bugs that would otherwise have been debugged at model prices, and a reference solution
  that cannot pass is proof the *checks* are wrong. Run it twice — a fixture that only
  sometimes satisfies its own verifier looks like a passing task.
- **Score outcomes, never paths.** Requiring a preferred run name, metric, evaluator name,
  mechanism, or tool call scores a hidden preference and rejects good solutions. Report
  those as stats instead. Both tasks have had a check rewritten for exactly this.
- **Specifying an outcome precisely enough to be *fair* often tells an unskilled agent
  exactly what bar to clear.** Treat the gate (did the skill auto-invoke?) as the primary
  signal; reward is a correctness canary.
- **Never infer an infrastructure fault from timing.** Partial evidence at a deadline is
  ambiguous between slow ingestion and an agent that only did part of the job. Excusing it
  means the task can never fail on partial work. Identify infra faults by exception type.
- **LangSmith ingestion is async and children land after their root.** Polling only until
  root runs appear fails correct solutions. Every check polls for the structure it needs.
- **Server-side evaluator feedback is invisible to a normal poll.** A local evaluator
  scores during `evaluate()`; one bound to a dataset runs server-side and lands much later,
  so a poll that stops at "every run is scored" never sees it. Ask `/runs/rules` which
  evaluators are bound to the dataset instead of waiting.
- **The evaluator skill teaches an older signature than the live docs.** Docs write
  evaluators as `def correct(outputs, reference_outputs)`; the skill teaches
  `(run, example)`. Both work. Never score the signature style, or a task bakes in
  staleness.
- **Evaluator rule names are workspace-global.** `langsmith evaluator delete NAME` removes
  every rule with that display name across all targets, and common names are heavily
  reused. Namespace per trial and delete by id.
- **`.env` values like `OPENAI_API_KEY=${LANGSMITH_API_KEY}` are references.** Use
  python-dotenv (harbor does); a naive parser forwards the literal string and the gateway
  403s.
- **Project prefix is `lsskills-`, deliberately not `bench-`** — skills-benchmarks'
  `sweep.py` uses `bench-` in the same workspace, and an orphan sweep on that prefix would
  delete its in-flight runs.
- **Cleanup must reach datasets and experiments, not just projects.** An experiment is a
  project named by whatever `experiment_prefix` the agent chose, so it cannot be found by
  run-id suffix — only through its `reference_dataset_id`.
- Harbor 0.18.0 hardcodes `build_args={}`, so tasks can't take Docker build args. Images
  install the latest `langsmith` CLI and stamp its version into
  `/opt/langsmith-cli-version.txt`; `--fresh-env` (`--force-build`) re-resolves it.
- **Probe tasks need their own directory.** `resolve_task` rejects paths, so a verifier
  fixture must be a throwaway sibling under `evals/`. Delete them afterwards.

## Watch out

- `--langsmith-experiment` implies `--keep`; the CI orphan sweep is disabled when it's on,
  or it would delete the traces the experiments point at.
- The CI artifact **excludes** `agent/**` because transcripts can capture env vars. So a
  CI-triggered failure gives you reward + failed checks but not the trajectory —
  reproduce locally to see what the agent did. Locally, `evals/jobs/**/agent/claude-code.txt`
  has everything.
- Back-to-back Docker stacks have intermittently failed DNS resolution, both in-container
  and host-side in `run.py`. Unrelated to any task; retry and space runs out.
- Neither task has been run with `--reps 3`, so flakiness is unmeasured.

## Outstanding

1. **CI secret.** `LANGSMITH_API_KEY` must be set on the repo; needs **admin** on
   `langchain-ai/langsmith-skills`. Until then the dispatch button does nothing.
2. `--reps 3` to measure flakiness.
3. An online-evaluator task. Blocked: creating a server-managed LLM-as-judge needs
   workspace-level LLM credentials that are not provisioned. Online *code* evaluators do
   work.
4. **Skill-freshness workflow** (separate from evals, by decision): check every
   `langsmith ...` command in every SKILL.md against the latest CLI's `--help`. One stale
   command has already been found and fixed by hand.
5. `langsmith-evaluator/SKILL.md` states that returning `{"metric_name": value}` from an
   evaluator will error, but rules doing exactly that run successfully. Resolve which is
   right before any verifier depends on it.
6. `langsmith` SDK prints a `list_runs()` deprecation (removal after Jan 2027) — port to
   `client.runs.query()` eventually.
7. **The fixture is the skill's own example.** `trace-instrument`'s `plain_app` reuses
   `rag_pipeline`/`retrieve_docs`/`generate_answer` verbatim from the trace skill. Until it
   diverges, the task rewards recall over transfer.
