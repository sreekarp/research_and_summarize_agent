import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()

REQUIRED_API_KEYS = ("TAVILY_API_KEY", "GROQ_API_KEY")
DEFAULT_TOPIC = "Impact of generative AI on education"


def parse_topic() -> str:
    parser = argparse.ArgumentParser(description="Research a topic on the web and print a cited Markdown report.")
    parser.add_argument("topic", nargs="?", default=DEFAULT_TOPIC, help=f'research topic (default: "{DEFAULT_TOPIC}")')
    args = parser.parse_args()

    missing = [key for key in REQUIRED_API_KEYS if not os.environ.get(key, "").strip()]
    if missing:
        parser.exit(2, f"Error: missing {' and '.join(missing)}. Add {'it' if len(missing) == 1 else 'them'} to a .env file in the repo root (see README).\n")

    # Imported after the key check: config builds the Groq clients, which need GROQ_API_KEY
    from config import MAX_TOPIC_CHARS
    topic = " ".join(args.topic.split())
    if not topic:
        parser.error("the topic must not be empty")
    if len(topic) > MAX_TOPIC_CHARS:
        parser.error(f"the topic is too long ({len(topic)} characters, max {MAX_TOPIC_CHARS})")
    return topic


async def main(topic: str) -> int:
    from graph.graph_builder import build_research_graph
    from config import MAX_REVISIONS
    from tools import llm
    from tools.errors import ServiceError

    print(f"\n>>> Researching Topic: '{topic}'\n")

    graph = build_research_graph()

    initial_state = {
        "topic": topic,
        "max_revisions": MAX_REVISIONS,
    }

    report, last_node = None, None
    try:
        async for output in graph.astream(initial_state):
            last_node = list(output.keys())[0]
            print(f"--- Executed Node: {last_node} ---")

            if last_node == "writer":
                report = output[last_node].get("report")
    except ServiceError as e:
        print(f"\n[!] Stopped: {e}", file=sys.stderr)
        return 1

    if llm.failed_calls:
        print(f"\n[!] {llm.failed_calls} LLM call(s) failed during the run; see the [!] lines above.")

    if not report:
        reason = ("none of the fetched pages produced cited findings; try rephrasing the topic"
                  if last_node == "writer" else "the planner returned no subtopics")
        print(f"\n[!] No report was produced: {reason}.", file=sys.stderr)
        return 1

    print("\n\n" + "="*50)
    print("                FINAL RESEARCH REPORT")
    print("="*50 + "\n")
    print(report)
    print("\n\n=== Research Complete ===")
    return 0

if __name__ == "__main__":
    # Reports often contain characters the Windows console code page can't encode (e.g. when output is redirected).
    # Line buffering makes progress show up in a redirected log file as it happens, not only when the run ends.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(asyncio.run(main(parse_topic())))
