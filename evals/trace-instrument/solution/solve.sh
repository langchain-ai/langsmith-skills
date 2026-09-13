#!/usr/bin/env bash
# Reference solution. Its job is to prove the verifier can be satisfied, so it
# uses the LangSmith SDK for the trace lookup (stable field names) rather than
# the CLI; agent runs are what exercise the CLI path the skill teaches.
set -euo pipefail

cd /workspace

# chain_app is built on LangChain: tracing needs env vars only, no code change.
export LANGSMITH_TRACING=true

# plain_app is not a framework app: wrap the client and decorate every nested
# function so the whole pipeline shows up as one trace tree.
cat > plain_app/main.py <<'PYEOF'
"""Support-policy answering pipeline on the OpenAI SDK, traced to LangSmith."""

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI())

DOCS = {
    "returns": "Unopened items may be returned within 30 days of delivery.",
    "shipping": "Standard shipping takes 3-5 business days.",
    "warranty": "Hardware carries a 12 month limited warranty.",
}


@traceable
def retrieve_docs(query: str) -> list[str]:
    hits = [text for topic, text in DOCS.items() if topic in query.lower()]
    return hits or list(DOCS.values())


@traceable
def generate_answer(question: str, docs: list[str]) -> str:
    context = "\n".join(docs)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": f"Answer only from this context:\n{context}"},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content or ""


@traceable
def rag_pipeline(question: str) -> str:
    docs = retrieve_docs(question)
    return generate_answer(question, docs)


def main() -> str:
    answer = rag_pipeline("What is the returns window?")
    print(answer)
    return answer


if __name__ == "__main__":
    main()
PYEOF

python chain_app/main.py
python plain_app/main.py

python - <<'PYEOF'
import os
import time
from pathlib import Path

from langsmith import Client

project = os.environ["LANGSMITH_PROJECT"]
client = Client()

for _ in range(24):
    roots = list(client.list_runs(project_name=project, is_root=True))
    plain = next((r for r in roots if r.name == "rag_pipeline"), None)
    chain = next((r for r in roots if r.name != "rag_pipeline"), None)
    if plain and chain:
        Path("/workspace/plain_trace.txt").write_text(str(plain.id))
        Path("/workspace/chain_trace.txt").write_text(str(chain.id))
        print(f"plain={plain.id} chain={chain.id} ({chain.name})")
        break
    time.sleep(5)
else:
    raise SystemExit(f"did not find both root runs in project {project}")
PYEOF
