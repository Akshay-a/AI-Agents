
from crewai import Agent, Task, Crew, Process, LLM
llm = LLM(
    model='ollama/llama3.1',
    base_url='http://localhost:11434'
)




# Define the agent
price_action_agent = Agent(
    role="Low time frame Trading Agent",
    goal="To look at LTF chart and provide the best possible trading set up for given crypto coin with take profit and stop loss. ",
    backstory=(
        "You are highly skilled at price action trader and open long and short trades based on the price action. "
        "With an eye for detail, you look for all lower time frames starting from 15 minutes time frame followed by 30 minutes and then 1 hour time frame and end analysis with 4 hour time frame. "
        "to mark the take profit and stop loss levels"
        "to provide reasoning for opening a long trade or short trade"
    ),
    verbose=True,
    llm=llm
)

# Define the task
split_bill_task = Task(
    description=(
        "Analyze the provided crypto coin and provide analysis to long or short the coin. \n\n"
        "Inputs:\n"
        "- Coin: {coin}\n\n"
        "Example Coin Description:\n"
        'BTCUSDT'
    ),
    expected_output=(
        "A detailed breakdown of Price action of BTCUSDT and explain all lower time frame analysis and provide the best possible trading set up with take profit and stop loss levels"
    ),
    agent=price_action_agent,
    output_file='technical_analysis.md'
)

# Create the crew
crew = Crew(
    agents=[price_action_agent],
    tasks=[split_bill_task],
    process=Process.sequential
)


# Inputs for the Crew
inputs = {
    "coin": "BTCUSDT"
}

# Execute the Crew task
result = crew.kickoff(inputs=inputs)
print(result)
