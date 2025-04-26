# AI - Deep Research Agent
This Repo contains Agent which mimics LLM's Ability of Deep Research.
Improved Version - https://github.com/Akshay-a/AI-Agents/tree/main/AI-DeepResearch/DeepResearchAgent/research_agent_backend

When Provided with a Prompt below are the conceptual steps:

1- Analyse the user’s query to understand the intent, scope, and key components. Natural language processing (NLP) techniques like tokenization, named entity recognition (NER), and semantic role labeling to identify topics, questions, and implicit goals.

2- Identify related Sub topics and internally construct a knowledge graph. (prolly need to dynamically update the knowledge with each step , new information may either rule out exising thesis or add a new criteria.) Each of the question type might have different construction of knowledge graph, but we can try to simulate BFS traversal for each query that 
we create and parse it to LLM. 
Step 2 can be enhanced further, but logically makes sense to do a BFS search on all constructed sub topics and create a research/analyse on overall topic.

3- explore each part of the graph systematically.

4- Create a chain of recursive questioning, Each can have a diff perspective like technical/Non techincal. Thinking from legal standpoint and ethical standpoint based on topic 
   May be pass counter opinion every now and then to re iterate on the step and think again , just like how we humans do.

5- Contextual Memory and Reasoning --> while we parse each sub query , at some point we might have huge context and reasoning sound will be difficutlt for an LLM
   So each step from 2-4 , we should try to make sure construction of relevant context only and should only add to reasoning. Also remove context/sub queries which are not relevant

6- Generate answer from accumlated knowlege from all the sub queries. try to create a structured response.

7- read the summary and if overall goal is achived ( like validation)




