# Research and Summarize Agent

[![CI](https://github.com/sreekarp/research_and_summarize_agent/actions/workflows/ci.yml/badge.svg)](https://github.com/sreekarp/research_and_summarize_agent/actions/workflows/ci.yml)

This is a sophisticated, multi-agent framework designed to research, process, and generate comprehensive reports on a given topic. By breaking down the research process into specialized roles, this system can efficiently gather, filter, and synthesize information from the web to produce high-quality, structured reports.

---

## 🚀 Getting Started

These instructions will get you a copy of the project up and running on your local machine.
### Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Python 3.10 or later**: LangGraph requires Python>=3.10.
* **pip**: The package installer for Python is required to install dependencies.
* **A Git client**: To clone the repository and manage source control.

Also get the API key from [Tavily](https://tavily.com/) for the web search functionality and API key from [Groq](https://groq.com/) to use the language models.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/sreekarp/research_and_summarize_agent.git
    cd research_and_summarize_agent
    ```

2.  **Create a virtual environment**: It is highly recommended to use a virtual environment to manage project-specific dependencies.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required packages**: All the necessary libraries are listed in the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables**: Create a `.env` file in the root directory of the project and add your API keys:
    ```
    TAVILY_API_KEY="YOUR_TAVILY_API_KEY"
    GROQ_API_KEY="YOUR_GROQ_API_KEY"
    ```

---

## 🔧 Usage

To run the summarization agent, execute the `main.py` script from the command line. You can provide a research topic as a command-line argument. If no topic is provided, it will default to "Impact of generative AI on education".

```bash
python main.py "The History of Ancient Rome"
```
The script will then initiate the research process, and you will see the agent's progress printed to the console, from the generation of subtopics to the final report. The report cites its sources with numbered markers like `[2]` and ends with a References list.

The script exits with code 0 when a report was written, 1 when no report could be produced (for example, no usable sources were found or an API key was rejected), and 2 for invalid input or missing API keys.

### The Research Process
The agent operates through a series of steps orchestrated by a state graph:

* **Planner**: Based on the input topic, the planner agent breaks it into 3-5 subtopics, each with its own web search query.

* **Searcher**: Runs the search queries in parallel and keeps only links that subtopic hasn't seen before. Social media sites and low-relevance results are skipped, and a topic about a recent year (for example "... in 2025") only searches pages published in that period. The summarizer and writer are also told the year, so later events don't leak into the report.

* **Retriever**: Fetches each page (public web addresses only, with size and time limits). When a site blocks the request or the link is a PDF, it uses the search engine's copy of the page instead. Each page becomes a numbered source.

* **Summarizer**: Reads each whole page, drops it if it is clearly off-topic, and otherwise summarizes it. It then condenses the summaries into bullet points for each subtopic. Every bullet must cite the sources it comes from.

* **Critiquer**: Checks whether the findings answer the topic well. If not, it suggests follow-up searches for the gaps; any subtopic that still has no findings is searched again too. The process loops back to the searcher once to fill them.

* **Writer**: Turns the cited bullet points into a well-structured Markdown report, keeping the citation markers. The Research gaps and References sections are added by the code from the actual results, so the model can't invent links or hide missing coverage.

### Guardrails
* LLM replies for planning, relevance, summarizing and critique use strict structured outputs, so they always match the expected format.
* Web content is treated as untrusted data in every prompt, to resist prompt injection.
* A single failed request is skipped instead of crashing the run, while problems that would fail every request (such as a rejected API key) stop the run with a clear message.
* If no source can be cited, no report is written, instead of producing one from nothing. Parts of the topic without sources are listed under "Research gaps" rather than filled in.

---
## 🧪 Testing

The test suite runs the whole pipeline offline: it fakes Groq, Tavily and every web page, so it needs no API keys and makes no network calls.

```bash
pip install -r requirements-dev.txt
ruff check .   # lint
pytest         # tests
```

GitHub Actions runs both on every push and pull request, on Python 3.10 and 3.12.

---
## 🛠️ Built With
* [**LangChain**](https://www.langchain.com/): Framework for developing applications powered by language models.
* [**LangGraph**](https://www.langchain.com/langgraph): Library for building stateful, multi-actor applications with LLMs.
* [**Tavily**](https://tavily.com/): Search API optimized for LLM-powered applications.
* [**Groq**](https://groq.com/): Provides the large language models used for the different agents.
* [**Beautiful Soup**](https://www.crummy.com/software/BeautifulSoup/): Python library for pulling data out of HTML and XML files.
