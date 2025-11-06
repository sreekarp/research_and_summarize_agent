# Research and Summarize Agent

This is a sophisticated, multi-agent framework designed to research, process, and generate comprehensive reports on a given topic. By breaking down the research process into specialized roles, this system can efficiently gather, filter, and synthesize information from the web to produce high-quality, structured reports.

---

## 🚀 Getting Started

These instructions will get you a copy of the project up and running on your local machine.
### Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Python 3.9 or later**: This project is built using Python>=3.9.
* **pip**: The package installer for Python is required to install dependencies.
* **A Git client**: To clone the repository and manage source control.

Also get the API key from [Tavily](https://tavily.com/) for the web search functionality and API key from [Groq](https://groq.com/) to use the language models.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone [https://github.com/sreekarp/summarize_agent.git](https://github.com/sreekarp/summarize_agent.git)
    cd summarize_agent
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
The script will then initiate the research process, and you will see the agent's progress printed to the console, from the generation of subtopics to the final report.

The Research Process
The agent operates through a series of steps orchestrated by a state graph:

* **Planner**: Based on the input topic, planner agent generates a list of relevant subtopics to guide the research.

* **Searcher**: For each subtopic, the searcher agent performs a web search and fetches the relevant articles and sources.

* **Retriever**: The content from the search results fetched by searcher agent is retrieved, and a relevance check is performed to filter out irrelevant information.

* **Summarizer**: The retrieved content is summarized into key bullet points for each subtopic.

* **Critiquer**: The generated summary is evaluated to ensure it is comprehensive. If not, the process may loop back to the searcher for another attempt.

* **Writer**: Once the critique is passed, this agent compiles the bullet points into a final, well-structured report in Markdown format.

---
## 🛠️ Built With
* [**LangChain**](https://www.langchain.com/): Framework for developing applications powered by language models.
* [**LangGraph**](https://www.langchain.com/langgraph): Library for building stateful, multi-actor applications with LLMs.
* [**Tavily**](https://tavily.com/): Search API optimized for LLM-powered applications.
* [**Groq**](https://groq.com/): Provides the large language models used for the different agents.
* [**Beautiful Soup**](https://www.crummy.com/software/BeautifulSoup/): Python library for pulling data out of HTML and XML files.
