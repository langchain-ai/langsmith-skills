"""Support-policy answering pipeline on the OpenAI SDK. Runs, but is not traced to LangSmith."""

from openai import OpenAI

client = OpenAI()

DOCS = {
    "returns": "Unopened items may be returned within 30 days of delivery.",
    "shipping": "Standard shipping takes 3-5 business days.",
    "warranty": "Hardware carries a 12 month limited warranty.",
}


def retrieve_docs(query: str) -> list[str]:
    hits = [text for topic, text in DOCS.items() if topic in query.lower()]
    return hits or list(DOCS.values())


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


def rag_pipeline(question: str) -> str:
    docs = retrieve_docs(question)
    return generate_answer(question, docs)


def main() -> str:
    answer = rag_pipeline("What is the returns window?")
    print(answer)
    return answer


if __name__ == "__main__":
    main()
