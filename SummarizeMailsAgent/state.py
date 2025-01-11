# src/state.py

from typing import TypedDict, List

class EmailState(TypedDict):
    emails: List[Dict[str, str]]
    actionable_emails: List[Dict[str, str]]
    action_items: List[str]
    max_messages: int