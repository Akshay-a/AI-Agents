Multi-Agent AI Research Assistant (MVP)
This project explores a more intelligent way to answer complex questions online.

Instead of just returning a list of links like a traditional search engine, the goal is to create an AI system that can understand a query, decide the best strategy, find or reason about answers, and synthesize a structured research report.

Think of it less like one giant brain and more like a small team of specialized AI assistants working together on your behalf.

🚀 Setup Instructions
Navigate to the AI-DeepResearch\DeepResearchAgent\research_agent_backend folder.

Create a .env file and add your Google API key:

bash
Copy
Edit
GOOGLE_API_KEY="your_api_key_here"
Run the backend application:

bash
Copy
Edit
uvicorn main:app --host 0.0.0.0 --port 8000 --reload


🧠 How It Works: The Agent Team Approach

At its core, the system uses a multi-agent architecture orchestrated by a central controller.

Planner Agent (The Strategist)
Analyzes the incoming query.

Decides if it requires fresh web search or logical reasoning.

Creates a dynamic, step-by-step plan for other agents to follow.

Specialist Agents (Executing the Plan)
Search Agent: Fetches relevant information from the web if required.

Reasoning Agent: Directly answers queries using internal knowledge when no web search is needed.

Filtering Agent: Cleans, deduplicates, and filters the search results to retain only the most relevant context.

Synthesizer/Analysis Agent: Combines the results into a clear, structured final report with sources linked at the bottom.

Orchestration and Communication

A central Orchestrator assigns tasks and manages workflow based on the Planner's output.

A Task Manager tracks progress for each task.

WebSockets are used to communicate real-time updates and deliver the final report to the user interface.

📈 Current Status (MVP)

The system dynamically plans and routes tasks through multiple agents.

Able to handle different types of queries (research, reasoning) and produce structured reports.

Backend is built with Python (FastAPI).

Currently integrates with Google Gemini models.

Future plans include integration with Llama 4 and DeepSeek R1 for enhanced reasoning on GPU.

🔥 Upcoming Enhancements

Building a React.js UI for better scalability and user experience.

Introducing multi-hop reasoning for complex queries to maximize intelligence even from smaller models.

Saving user interactions to a database to offer a hyper-personalized discover feed based on past queries (similar to Perplexity’s Comet project).

🌟 Vision

The aim is to create a system that genuinely assists with research and knowledge discovery, moving beyond simple keyword matching toward synthesized understanding.

This is an early-stage open source project, and contributions, feedback, and ideas are warmly welcomed.

🛠️ Get Involved

If this project sparks any ideas or improvements in your mind, feel free to reach out!
Email me at aapsingi95@gmail.com
Ping me on linkdelin- https://www.linkedin.com/in/a-akshay-kumar/

Even a ⭐ on the repo would mean a lot!


