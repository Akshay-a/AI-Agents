create .env file in AI-DeepResearch\DeepResearchAgent\research_agent_backend folder
set up google_api_key in .env  --> GOOGLE_API_KEY=""
run the main.py app -> "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

Project Description:
Multi-Agent AI Research Assistant (MVP)
This project is an exploration into building a more intelligent way to get answers to complex questions online. Instead of just getting a list of links like a standard search engine, the goal here is to have an AI system that can actually understand a query, figure out the best way to find or reason about the answer, and then synthesize the information into a coherent report.
Think of it less like a single giant brain trying to know everything, and more like a small team of specialized AI assistants working together on your behalf.
How it Works (The Agent Team Approach):
At its core, this system uses a multi-agent architecture orchestrated by a central controller. Here's a simplified look at the workflow:
The Planner Agent (The Strategist): When you ask a question, the first agent to look at it is the Planner. Its job is to analyze your query and decide on the best strategy. Does the question need up-to-the-minute information from the web? Or is it something that requires general knowledge or logical reasoning? Based on this, it creates a dynamic, step-by-step plan (like a mini project plan) outlining which other agents need to get involved.
Executing the Plan (The Specialists): The central orchestrator takes the plan and assigns tasks to the specialist agents:
Search Agent: If the plan requires web information, this agent takes the specific search terms defined by the Planner and goes out to fetch relevant web pages.
Reasoning Agent: If the Planner decided the query could be answered directly using the AI's internal knowledge, this agent gets the task to think through the problem and generate an answer.
Filtering Agent: After the Search Agent brings back raw data, the Filter Agent sifts through it, cleaning it up and consolidating the useful bits.
Synthesizer/Analysis Agent (The Writer): This is a crucial agent. It takes the filtered information from the web searches or the answer from the Reasoning Agent and its main job is to understand and synthesize it all. It then writes the final, structured report (usually in Markdown) that actually answers your original query.
Orchestration & Communication: Behind the scenes, an Orchestrator manages the overall flow, taking the plan from the Planner, dispatching tasks to the correct agents, keeping track of progress (which steps are done, which failed), and ensuring the output of one step can be used by the next. A Task Manager keeps track of all the individual tasks defined in the plan. We use WebSockets to communicate progress (like which step is done) and the final report back to the user interface.
Current Status (MVP):
This is an early version (MVP). The core architecture with the Planner generating dynamic plans and the different agents executing them is functional. It can handle different types of queries (research vs. reasoning) and produce a final report. The backend is built with Python (FastAPI) and uses Large Language Models (right now i've only used Google Gemini, but will integrate with llama4/Deepseek R1 reasoning model and run on GPU) for the planning, reasoning, and synthesis steps.
Goal & Vision:
The aim is to create a system that genuinely assists with research and knowledge discovery, going beyond simple keyword matching to provide synthesized understanding. By open-sourcing this, I hope to collaborate and improve upon the planning intelligence, the quality of synthesis, and the overall robustness of the multi-agent approach.

if you have ideas and want to collaborate on this, email me at aapsingi95@gmail.com
or ping me on linkdelin- https://www.linkedin.com/in/a-akshay-kumar/
