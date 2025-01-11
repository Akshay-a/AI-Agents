# src/Crew/task.py

from crewai import Task
from .agents import EmailAnalyzerAgent
from .agents import SummaryAgent

def analyze_email(email: dict) -> bool:
    agent = EmailAnalyzerAgent()
    return agent.is_actionable(email)

def summarize_email(email: dict) -> str:
    agent = SummaryAgent()
    return agent.summarize(email)

"""class AnalyzeEmailTask(Task):
    def __init__(self):
        super().__init__(
            name="Analyze Email",
            description="Determine if the email contains actionable items",
            expected_output="Boolean indicating if email is actionable",
            agent=EmailAnalyzerAgent(),
            tools=[analyze_email]
        )

class SummarizeEmailTask(Task):
    def __init__(self):
        super().__init__(
            name="Summarize Email",
            description="Summarize the actionable items from the email",
            expected_output="A string summary of the actionable items",
            agent=SummaryAgent(),
            tools=[summarize_email]
        )
"""
class AnalyzeEmailTask(Task):
    def __init__(self):
        super().__init__(
            description=(
                "Analyze the provided email content to identify actionable items. \n\n"
                "The Email Body might contain few sections which are html based or might also be images. Think accordingly.\n\n"
                "Inputs:\n"
                "- Email Subject: {subject}\n"
                "- Email Body: {body}\n\n"
                "Determine if the email requires action and describe the action."
            ),
            expected_output=(
                "A boolean indicating if the email is actionable and a brief description of the action if applicable."
            ),
            agent=EmailAnalyzerAgent()
        )

class SummarizeEmailTask(Task):
    def __init__(self):
        super().__init__(
            description=(
                "Summarize the actionable items from the email into todo list format. \n\n"
                "The Email Body might contain few sections which are html based or might also be images. Think accordingly.You should ignore the image part of the body and treat it as a distraction\n\n"
                "Inputs:\n"
                "- Email Subject: {subject}\n"
                "- Email Body: {body}\n\n"
                "Output should be formatted as 'Task: <task description>'."
            ),
            expected_output=(
                "A formatted string representing the actionable item as a todo."
            ),
            agent=SummaryAgent()
        )