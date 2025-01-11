# src/main.py
from .src.Graph import create_graph
from .src.state import EmailState

if __name__ == "__main__":
    graph = create_graph()
    initial_state: EmailState = {
        "emails": [],
        "actionable_emails": [],
        "action_items": [],
        "max_messages": 20
    }
    result = graph.invoke(initial_state)
    print("Todo list has been updated with action items.")