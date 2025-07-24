import sys
import asyncio
from dotenv import load_dotenv
load_dotenv()
from graph.graph_builder import build_research_graph
from config import MAX_REVISIONS


async def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "Impact of generative AI on education"
    print(f"\n>>> Researching Topic: '{topic}'\n")

    graph = build_research_graph()

    initial_state = {
        "topic": topic,
        "max_revisions": MAX_REVISIONS,
    }

    async for output in graph.astream(initial_state):
        node_name = list(output.keys())[0]
        print(f"--- Executed Node: {node_name} ---")

        if node_name == "writer":
            print("\n\n" + "="*50)
            print("                FINAL RESEARCH REPORT")
            print("="*50 + "\n")
            print(output[node_name].get("report"))

    print("\n\n=== Research Complete ===")

if __name__ == "__main__":
    asyncio.run(main())