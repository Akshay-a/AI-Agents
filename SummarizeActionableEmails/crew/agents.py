# src/Crew/agents.py

from crewai import Agent, Task, Crew, Process, LLM

llm = LLM(
    model='ollama/llama3.1',
    base_url='http://localhost:11434'
)
class EmailAnalyzerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Email Analyzer",
            role="Analyzes emails for actionable items",
            goal="Determine if an email requires an action",
            backstory="""I am an expert in email analysis, trained to sift through 
                        email content to identify tasks or actions that need to be taken.
                        Do not Hesitate to reject any email that you think is not actionable and don't make assumptions if the email does not have any direct action item.""",
                        llm=llm,
                        verbose=True
        )

    def is_actionable(self, email: dict) -> bool:
        # Here, we would integrate with an LLM, but for now, let's use a placeholder
        return 'action' in email['body'].lower() or 'task' in email['body'].lower()

class SummaryAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Email Summarizer",
            role="Summarizes actionable emails",
            goal="Create concise summaries of actionable items",
            backstory="""I specialize in summarizing email content into clear, 
                        actionable tasks.I might also reject few emails which are not actionable.""",
                        llm=llm,
                        verbose=True
        )

    def summarize(self, email: dict) -> str:
        # Placeholder for LLM summarization
        return f"{email['subject']}: {email['body'][:50]}..."