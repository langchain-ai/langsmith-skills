"""Album lookup agent built on LangChain. Runs, but is not traced to LangSmith."""

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

TRACK_COUNTS = {"Greatest Hits": 57, "Minha Historia": 34, "Unplugged": 30}


@tool
def get_track_count(album: str) -> int:
    """Return the number of tracks on the named album."""
    return TRACK_COUNTS.get(album, 12)


agent = create_agent(
    ChatOpenAI(model="gpt-4o-mini", temperature=0),
    [get_track_count],
    system_prompt="Answer album questions using the get_track_count tool.",
)


def main() -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "How many tracks are on Greatest Hits?"}]}
    )
    answer = result["messages"][-1].content
    print(answer)
    return answer


if __name__ == "__main__":
    main()
