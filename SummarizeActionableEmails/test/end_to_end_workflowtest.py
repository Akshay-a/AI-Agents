# tests/test_workflow.py

import unittest
from src.Graph import create_graph
from src.state import EmailState


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.graph = create_graph()

    def test_basic_workflow(self):
        # Mock email data
        mock_emails = [
            {"subject": "Test email 1", "body": "This email needs an action", "sender": "test@example.com"},
            {"subject": "Test email 2", "body": "This is just an update", "sender": "test@example.com"}
        ]
        initial_state: EmailState = {
            "emails": mock_emails,
            "actionable_emails": [],
            "action_items": [],
            "max_messages": len(mock_emails)
        }

        result = self.graph.invoke(initial_state)

        # Assertions
        self.assertTrue(len(result['action_items']) > 0)  # At least one action item should be created
        self.assertIn("Test email 1", result['action_items'][0])  # Check if the first email is actionable
        self.assertEqual(len(result['action_items']), 1)  # Only one email should be actionable

if __name__ == '__main__':
    unittest.main()