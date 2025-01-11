# src/Graph.py

from langgraph.graph import StateGraph, END
from src.state import EmailState
from src.Nodes import fetch_emails, process_email, summarize_actions, write_to_todo, end_process


def create_graph():
    workflow = StateGraph(EmailState)
    
    # Adding nodes to the graph
    workflow.add_node("fetch_emails", fetch_emails)
    workflow.add_node("process_email", process_email)
    workflow.add_node("summarize_actions", summarize_actions)
    workflow.add_node("write_to_todo", write_to_todo)
    workflow.add_node("end_process", end_process)
    
    # Define conditional edges
    def has_actionable_emails(state: EmailState) -> str:
        if state['actionable_emails']:
            return "summarize_actions"
        else:
            return "end_process"  # Skip summarization if no actionable emails

    def email_fetch_failed(state: EmailState) -> str:
        # This could be expanded to check for specific errors or conditions
        if not state.get('emails'):
            print("No emails could be fetched or processed. Ending workflow.")
            return "end_process"
        return "process_email"

    # Connect nodes with conditions
    workflow.add_edge("fetch_emails", "process_email")  # Default transition if no error
    workflow.add_conditional_edges("fetch_emails", email_fetch_failed, {
        "process_email": "process_email",
        "end_process": "end_process"
    })
    '''workflow.add_conditional_edges("process_email", has_actionable_emails, {
        "summarize_actions": "summarize_actions",
        "end_process": "end_process"
    })
    workflow.add_edge("summarize_actions", "write_to_todo")
    '''
    workflow.add_edge("process_email", "write_to_todo")
    workflow.add_edge("write_to_todo", "end_process")
    
    # Set entry point
    workflow.set_entry_point("fetch_emails")
    
    return workflow.compile()

if __name__ == "__main__":
    graph = create_graph()
    initial_state: EmailState = {
        "emails": [],
        "actionable_emails": [],
        "action_items": [],
        "max_messages": 20
    }
    result = graph.invoke(initial_state)
    print("Final State:", result)