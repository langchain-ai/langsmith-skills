# Author, preview, and publish without the code box

Use this recipe when someone asks their coding agent to create an online
evaluator from a project link, test it on selected traces, and publish it only
after reviewing results. The agent runs the commands; the user does not need
to copy code into LangSmith. This is workflow guidance using existing APIs,
not a new hosted preview service.

## 1. Establish the target and author locally

Resolve the project link to its endpoint, workspace, and project ID. Verify
credentials with a read-only request. Follow [Trace inspection](trace-inspection.md)
to inspect representative traces, including failures and missing outputs; ask
about ambiguous scoring criteria rather than guessing field paths. Check
existing evaluators and attachments before choosing a new name.

Keep the source, sample export, and preview report in the user's working
project, outside this skills repository. Treat trace exports as sensitive;
exclude them from git and do not attach raw payloads to a shared report.
Export a bounded selection of run dictionaries as a JSON array, preserving
string `id` values and the fields the evaluator needs. Distinguish production
samples from synthetic edge cases and human-labeled calibration examples.

Choose the execution path before authoring:

| Evaluator | Preview | Publication |
| --- | --- | --- |
| Standalone Python deterministic online code | Helper below, using `perform_eval(run)` and a feedback mapping | Workspace evaluator SDK with identical source bytes |
| Managed LLM judge | Bounded local calibration with the exact prompt, model settings, structured schema, and field mapping | Workspace SDK with an immutable prompt commit |
| Code needing LangChain, external services, or other unsupported packages | Local SDK evaluation | Keep external execution and post feedback with the SDK; do not promise it can run in the hosted code sandbox |
| Thread-level or JavaScript evaluator | Supported SDK/CLI test path for that contract | Supported attachment API for that contract; the Python run-level helper does not apply |

Read [LangSmith API](langsmith-api.md) for SDK requirements and contracts.
The CLI wrapper in `langsmith-evaluator` has a different return contract from
this direct workspace SDK path. Do not upload a feedback-mapping function
through that wrapper or silently rewrite a tested function at publication.

## 2. Preview without production attachment

For standalone Python code, use the bundled helper. Resolve `SKILL_DIR` to the
installed `langsmith-online-eval-engineering` skill directory, not the user's
project directory:

```bash
python "$SKILL_DIR/scripts/preview_code_evaluator.py" preview \
  --source evaluator.py --runs selected-runs.json --report preview.json
```

The helper uses only the Python standard library. It executes **trusted,
reviewed local source with the current process's permissions**, not in an
isolation sandbox. Never execute code copied from a trace. Run it in a
restricted development environment without production credentials and with a
bounded execution timeout. The helper makes no LangSmith calls itself, but
imported or evaluator code can perform side effects, network calls, or print
sensitive data. Review that code before running it.

The supported function is synchronous `perform_eval(run)`, returning a
nonempty dictionary of feedback keys to finite numeric or boolean scores.
The report contains run IDs, scores, exception types, and SHA256 hashes of
source and sample bytes; it does not copy inputs, outputs, or exception
messages. Protect even this report as workspace data. A nonzero exit means
stop and fix the preview. Errors during source loading block the whole preview.

Show the user a compact score table and disagreements against their labels,
plus missing-field cases and execution errors. Explain the rubric and score
scale. For deterministic code there is no model-token cost; for LLM judges,
show measured usage when available or a clearly labeled estimate, not a
fabricated cost. If the rubric changes, rerun on the same calibration sample
and explain which results changed.

A successful local run is **not hosted compatibility proof**. Check the current
package allowlist, network restrictions, function signature, and return
contract. Use a supported non-attaching hosted test endpoint if available;
otherwise state that hosted execution remains unverified. Never attach a
production rule or call feedback creation just to simulate a preview.

For LLM judges, keep a manifest of the exact prompt commit, structured schema,
model/provider settings, field mapping, and calibration trace IDs. Freeze that
configuration before presenting results. Local model calls still incur cost
and must fit the user's authorized budget. Disable automatic tracing for
preview calls unless the user authorized recording them.

## 3. Review the proposed publication

Present one reviewable configuration:

```text
Endpoint / workspace / project ID:
Evaluator name / new or existing evaluator ID:
Type / run or thread scope:
Source SHA256 or immutable prompt commit and model configuration:
Feedback keys / scales / rubric:
Preview sample count / failures / calibration disagreements:
Hosted compatibility: verified or specific remaining limitation
Filter / sampling rate / enabled state:
Weekly spend limit / retention impact:
Backfill: off unless explicitly requested
Existing attachments affected by an update:
```

For a request to test and show results before enabling, stop here and wait for
authorization of this configuration. Existing explicit authorization to publish
this exact configuration is sufficient; do not add a redundant approval gate.
A generic request to explore or preview is not authorization to attach a rule,
backfill production history, or update a shared evaluator. Prefer a new
version when modifying an evaluator would change other attachments.

## 4. Publish the tested artifact, then verify

Immediately before publishing standalone Python code, verify the report:

```bash
python "$SKILL_DIR/scripts/preview_code_evaluator.py" verify \
  --source evaluator.py --runs selected-runs.json --report preview.json
```

Verification detects source/sample drift and failed previews. It is not an
approval signature, dependency lock, sandbox, or hosted runtime test. Keep the
source standalone; changes to dependencies or runtime require retesting too.

Read the source bytes once, compare their SHA256 to the reviewed report in
the publishing process, and pass that same decoded content to
`client.evaluators.create` as `code_evaluator.code`. Do not regenerate or
wrap the function. For an LLM judge, publish the reviewed immutable prompt
commit and configuration; do not substitute `latest`. If any reviewed code,
prompt, model, mapping, or rule setting changes, rerun the affected preview
and renew authorization when it changes the approved scope or behavior.

Retrieve the created evaluator by ID and compare its source/configuration with
the reviewed artifact before attaching it. Resolve the exact project ID and
use the current documented attachment API, following
[LangSmith API](langsmith-api.md). Do not guess an endpoint or fall back to
asking the user to paste source into a code box. If the installed SDK/CLI
cannot attach it, report the specific missing capability and leave it
unattached rather than claiming deployment succeeded.

Re-read the attachment and verify evaluator ID, project ID, enabled state,
filter, sampling, and backfill. Inspect initial execution logs and scores when
available. Distinguish “published but unattached,” “attached, awaiting first
execution,” and “executed successfully.” A publication failure must not be
reported as a successful deployment. Do not retry an uncertain create blindly;
look for the newly created resource first.

Return the actual LangSmith evaluator/project link, version/hash, preview
summary, verified rule scope, and any unresolved runtime limitation. Record the
new rule ID so disabling it is targeted; do not delete every rule sharing a
name or promise rollback of scores or retention changes already applied.
