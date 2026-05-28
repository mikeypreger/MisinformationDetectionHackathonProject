# agents.py
import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def agent_skeptic(text):
    """Looks at the text and identifies emotional manipulation or logical fallacies."""
    # TODO: Write a prompt that makes the LLM act like a harsh skeptic
    pass

def agent_researcher(text, search_results):
    """Compares the text against real web search results."""
    # TODO: Write a prompt that forces the LLM to only use provided search results
    pass

def agent_judge(skeptic_report, researcher_report):
    """Takes the reports from the other agents and makes a final True/False/Misleading call."""
    # TODO: Write a prompt that synthesizes the other agents' outputs
    pass