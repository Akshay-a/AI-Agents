# src/state.py

from typing import TypedDict, List

"""
This class contains state which will be passed through each node and updated.
Each node will update the state and return it to the next node.
"""

class EmailState(TypedDict):
    emails: List[dict[str, str]]
    actionable_emails: List[dict[str, str]]
    action_items: List[str]
    max_messages: int