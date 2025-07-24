# tools/prompts.py
from langchain_core.prompts import PromptTemplate

planner_prompt = PromptTemplate.from_template(
    """You are a research planner. Your goal is to break down a complex topic into 3-5 distinct,
    researchable subtopics.

    Return these subtopics as a Python-parseable list of strings.

    Topic: {topic}

    Example:
    Topic: The history of artificial intelligence
    Response:
    ```python
    ["Key pioneers and their contributions", "Evolution of neural networks", "The AI winter and its impact", "Modern breakthroughs in deep learning"]
    ```
    """
)

relevance_check_prompt = PromptTemplate.from_template(
    """You are a relevance-checking AI. Given a subtopic and a snippet of text from a webpage,
    determine if the text is relevant to the subtopic.

    Respond with a single word: 'relevant' or 'irrelevant'.

    Subtopic: {subtopic}
    Text Snippet:
    ---
    {text}
    ---
    """
)

map_summarize_prompt = PromptTemplate.from_template(
    """Summarize the following text, focusing on the key facts and figures related to the subtopic.
    Be concise and extract the most important information.

    Subtopic: {subtopic}
    Text:
    ---
    {text}
    ---
    """
)

reduce_bullets_prompt = PromptTemplate.from_template(
    """You are a research synthesizer. You will be given a subtopic and a collection of summaries from different sources.
    Your task is to consolidate this information into 3-5 clear, concise bullet points.

    Focus on accuracy and clarity. Do not add information that is not present in the provided summaries.

    Subtopic: {subtopic}
    Summaries:
    ---
    {summaries}
    ---

    Return only the bullet points.
    """
)

critique_prompt = PromptTemplate.from_template(
    """You are a research quality analyst. Your task is to evaluate a research summary based on the original topic.
    The summary is broken down by subtopic.

    Review the summary and determine if it provides a comprehensive and satisfactory answer to the original topic.

    Provide a one-sentence critique and then, on a new line, a single word: 'complete' or 'incomplete'.

    Original Topic: {topic}
    Research Summary:
    ---
    {summary_text}
    ---

    Example Response:
    The summary lacks detail on the practical applications.
    incomplete
    """
)

writer_prompt = PromptTemplate.from_template(
    """You are an expert report writer. Your task is to create a comprehensive, well-structured research report
    in Markdown format based on the provided bullet points for various subtopics.

    The report should have a clear title, an introduction, sections for each subtopic, and a concluding summary.
    Synthesize the information into a flowing narrative, not just a list of bullets.

    Original Topic: {topic}
    Bullet Points:
    ---
    {summary_text}
    ---
    """
)