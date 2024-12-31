
from crewai import Agent, Task, Crew, Process, LLM
llm = LLM(
    model='ollama/llama3.1',
    base_url='http://localhost:11434'
)




# Define the agent
university_agent = Agent(
    role="University Descriptor",
    goal="To provide a detailed description of a university based on the given inputs.Mentions pros and cons of studying in the university and if university provides placements or not.",
    backstory=(
        "You are highly skilled at quickly learning about universities. "
        "With an eye for detail, you ensure fairness when describing universities. "
        "to clearly describe the university and write about pros and cons"
        "to provide which courses are offered best in university"
    ),
    verbose=True,
    llm=llm
)

# Define the task
split_bill_task = Task(
    description=(
        "Analyze the provided university name and provide feedback on the university. \n\n"
        "Inputs:\n"
        "- University: {universityName}\n\n"
        "Example University Description:\n"
        'University of Sydney'
    ),
    expected_output=(
        "A detailed breakdown based on university, on basis of courses offered, placements, pros and cons of studying in the university"
    ),
    agent=university_agent,
    output_file='bill_output.md'
)

# Create the crew
crew = Crew(
    agents=[university_agent],
    tasks=[split_bill_task],
    process=Process.sequential
)


# Inputs for the Crew
inputs = {
    "universityName": "University of Sydney"
}

# Execute the Crew task
result = crew.kickoff(inputs=inputs)
print(result)
