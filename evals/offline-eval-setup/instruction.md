We're about to start making changes to the app in `support_app/`, and we have no
regression checks on it at all. Our test cases are in `test_cases.json`.

Set us up in LangSmith so we can catch regressions:

1. Get those test cases in as a dataset. Name it using the value of the
   `LANGSMITH_DATASET` environment variable.
2. Score the app against every one of the cases.
3. Write the per-case scores to `/workspace/results.json`, as a JSON list with one
   object per test case giving that case's policy topic and the score it received.

Leave `support_app/` itself alone — we want to know how it behaves today, not how it
behaves after a fix.
