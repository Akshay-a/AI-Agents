# src/nodes.py

from typing import Dict
from src.state import EmailState
from src.tools import GmailIntegration
from src.utils import RESTRICTED_EMAILS
from crew.agents import EmailAnalyzerAgent, SummaryAgent
from crew.task import AnalyzeEmailTask,SummarizeEmailTask
from crewai import Agent, Task, Crew, Process

def fetch_emails(state: EmailState) -> EmailState:
    """Fetch emails from Gmail."""
    gmail_tool = GmailIntegration()
    gmail_tool.authenticate()
    state['emails'] = gmail_tool.get_latest_emails(state['max_messages'])
    print(f"Fetched {len(state['emails'])} emails.")
    #print(state['emails'])
    print("Fetched emails.")
    return state

def process_email(state: EmailState) -> EmailState:
    print("Processing emails.")
    """Process each email to determine if it's actionable."""
    state['actionable_emails'] = []
    for email in state.get('emails', []):
        if email['sender'] not in RESTRICTED_EMAILS and 'quora' not in email['sender']:  # Restrict creating todo list from certain emails 
            print("calling crew agent to analyze email")

            crew = Crew(
            agents=[EmailAnalyzerAgent()],  # Use the analyser agent associated with the task
            tasks=[AnalyzeEmailTask()],
            process=Process.sequential,
            verbose=True)

            result = crew.kickoff(inputs={
                "subject": email['subject'],
                "body": email['body']})
            print(f"First crew agent returned below action item {result}")
            if result :
                #action described by agent , this can be optionally used as part of state  result.get('action', 'No action described')
                state['actionable_emails'].append(email)
                state['action_items'].append(result)
    return state

def summarize_actions(state: EmailState) -> EmailState:
    print("Summarizing actionable emails.")
    """Summarize actionable items from emails."""
    state['action_items'] = []
    for email in state.get('actionable_emails', []):
        print("calling crew agent to Summarize emails")
        crew = Crew(
            agents=[SummaryAgent],
            tasks=[SummarizeEmailTask],
            process=Process.sequential
        )
        result = crew.kickoff(inputs={
            "subject": email['subject'],
            "body": email['body']
        })
        if result:
            state['action_items'].append(result)
        #action_item = f"{email['subject']}: {email['body'][:50]}..."
        #state['action_items'].append(action_item)
    return state

def write_to_todo(state: EmailState) -> EmailState:
    print("Writing action items to file.")
    """Write action items to a local file."""
    with open('todo_list.txt', 'w') as file:
        for item in state.get('action_items', []):
            file.write(f"{item}\n")
    return state

def end_process(state: EmailState) -> EmailState:
    """End the workflow."""
    print("Processing completed.")
    return state