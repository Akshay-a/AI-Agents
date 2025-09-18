The app prototype is done on local machine to use in production define evaluation criteria and test and refine on top of it.
existing methods can be extended for more customizations, Feel free to use this in your agentic systems which needs
real time web scraping and targettd information retreival from web. 
This is powered by duckduckgo and crawl4ai and chromadb and LLM used for inference is llama3.2-8b via GROQ

This is a Web scraper agent that is planned to be a part of larger agentic system where agents need
real time information access like documentation, pullling detailed answers from large webpages, targetted search on large PDFs online, Making this agent open source.

This Agent takes input as a query:
Checks for VectorDB Embeedinds in memory first and if not found then runs web search.

run a duckduckgo search----> get top 20 URLS------> 

Below process happens parallely for all fetched URLs ( crawl4AU handles this async behaviour under the hood)
take each URL --> if it is PDF----> run PDFStrategy  ---->pull markdown format---> Insert to RAG
                           ---> else HTML strategy  ------> pull extracted content ( already filtered by LLM ) --> Insert to RAG

The Reasoning is draawn from the RAG and the input question is saved as id in the RAG index 

When the Agent needs more sophisticated information that is part of already fetched information, The Agent takes the input
and checks in cache , if not found it will run a new duckduckgo search and fetch the information and insert to RAG else it directly referes to the nearest 10 embeddings and uses LLM to generate the answer.


To test this agent -->

- paste the test URL ( or set of URLs) in test.py file and run it , you can validate if the markdown files are created in output folder
- To test the RAG Retrieval , paste the URLs in test_2 and update question that you want to test on , run it and validate if Agent gives nearest answer. 