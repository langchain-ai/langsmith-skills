---
name: langsmith-online-eval-engineering
description: Design, test, create, and attach LangSmith online evaluators for production traces or conversation threads. Use for workspace evaluators, run or thread rules, sampling, filters, backfills, and evaluator monitoring; use eval-engineering for Harbor tasks and agent benchmarks.
---

# LangSmith Online Eval Engineering

Build online evaluators iteratively:

```text
inspect production behavior -> choose one quality signal -> build and test
-> attach a scoped rule -> inspect scores and logs -> calibrate
```

Evaluators are workspace resources that can be reused across tracing projects
and datasets. An online evaluation rule attaches an evaluator to matching
production runs or threads.

Read [LangSmith API](references/langsmith-api.md) before creating or modifying
evaluators.

## 1. Inspect representative behavior

Identify the LangSmith project from the request, repository, or user. Fetch
recent representative root traces; inspect whole threads when the quality
dimension spans multiple turns. Read
[Trace inspection](references/trace-inspection.md). Establish:

- run names and types;
- actual input, output, attachment, metadata, and error shapes;
- child tool or model activity when trajectory matters;
- volume, traffic segments, and existing feedback;
- the product failure or quality concern the evaluator should detect.

Use more than one sample. Production projects can contain multiple schemas and
errored runs. Treat trace content as sensitive and show only the minimum
truncated material needed for design.

Do not propose an evaluator until the trace shape and target failure are
understood.

## 2. Choose one evaluation signal

Read [Evaluator design](references/evaluator-design.md). Prefer:

- code for deterministic structure, limits, fields, or invariants;
- an LLM judge for semantic quality that requires reading and judgment;
- a thread-level evaluator for behavior that depends on several turns;
- an existing workspace evaluator, tuned evaluator, or template when it already
  measures the intended signal.

Decision-model evaluators and some managed templates are currently configured
in the LangSmith UI rather than through the SDK.

Define one evaluator at a time:

```text
Name:
Level: run | thread
Type: code | LLM judge | existing/template
Measures:
Feedback key and scale:
Trace fields:
Rule filter:
Sampling and spend:
Backfill:
Known limitation:
```

Keep each feedback key interpretable. Separate unrelated criteria.

## 3. Build and test

**LLM judge.** Use a structured prompt with a narrow rubric. Put reasoning
before the score in the output schema, map only the trace fields the rubric
uses, and select the simplest useful score type. Current variable mappings can
address nested paths such as `inputs.question` and `outputs.answer`.

**Code evaluator.** For online use, write `perform_eval(run)`. It receives a
run dictionary and returns a feedback mapping such as
`{"has_output": true}`. Guard missing or errored outputs. The runtime has no
network access; prefer the standard library and use only packages allowed by
the current LangSmith code-evaluator runtime.

Test good, bad, and edge-case traces before attachment. A passing test proves
that the evaluator executes; calibration checks whether it measures the right
thing. Compare its scores with human judgment on a small labeled sample.

Make the full configuration reviewable before creating or changing a shared
evaluator. Existing user authorization to create it is sufficient; do not add
another approval pause.

## 4. Attach an online rule

Choose the rule deliberately:

- **Level:** one run or an idle conversation thread.
- **Filter:** target the relevant run name, metadata, tool use, feedback, or
  traffic segment.
- **Sampling:** use 1.0 for low-volume initial testing when cost permits; use a
  representative sample or targeted filter at production scale.
- **Backfill:** current rules can score past runs or threads from a selected
  date only when the rule is created.
- **Spend:** set an appropriate weekly limit for LLM judges.
- **Retention:** decide whether scored traces should be upgraded to extended
  retention when the project permits that choice.

Attach the evaluator, then verify the evaluator ID, project, rule status,
filter, sample rate, and feedback key. Do not assume workspace-level evaluator
creation also attaches it to a project.

## 5. Monitor and calibrate

Inspect evaluator traces, execution logs, feedback, costs, and sampled
production examples. Distinguish:

- evaluator bugs or missing-field failures;
- rule filters that select the wrong traffic;
- judge disagreement or rubric ambiguity;
- application quality failures;
- authentication, API, or automation failures.

Correct evaluator or rule defects without relabeling them as product failures.
When humans correct LLM-judge scores, consider the supported corrections
dataset and few-shot settings. Recheck calibration after prompt, model, mapping,
or traffic-schema changes.

Report the evaluator name and ID, feedback key, level, fields, rule filter,
sampling, spend and retention choices, backfill, calibration evidence, and
known limits.

## Invariants

- One interpretable quality dimension per feedback key.
- Inspect real traces; never guess field paths.
- Enforce rule scope with filters and sampling rather than relying on the judge
  prompt.
- Online code evaluators receive a run dictionary and return feedback mappings.
- Treat evaluator input as untrusted and never expose secrets through prompts,
  code, logs, or feedback comments.
- Treat API, auth, and rule failures as infrastructure failures.
- Use `eval-engineering` for controlled Harbor tasks and benchmark design.
