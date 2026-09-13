"""Support-policy lookup app. Deterministic: a fixed table, no LLM call.

The chain is a real LangChain Runnable so it traces to LangSmith like any other
app, but its answers never vary. That keeps an evaluation over it reproducible
and free.
"""

from langchain_core.runnables import RunnableLambda

POLICIES = {
    "returns": "Unopened items may be returned within 30 days of delivery.",
    "shipping": "Standard shipping takes 3-5 business days.",
    "warranty": "Hardware carries a 12 month limited warranty.",
}


def lookup(payload: dict) -> dict:
    topic = str(payload.get("topic", "")).strip().lower()
    return {"answer": POLICIES.get(topic, "No policy on file for that topic.")}


chain = RunnableLambda(lookup).with_config(run_name="support_app")


def answer(topic: str) -> str:
    return chain.invoke({"topic": topic})["answer"]


def main() -> None:
    for topic in POLICIES:
        print(f"{topic}: {answer(topic)}")


if __name__ == "__main__":
    main()
