import csv
import os
from pathlib import Path
import logging
import asyncio

from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain_community.llms import Ollama
from pydantic import BaseModel, SecretStr
from typing import Optional
from langchain_ollama import ChatOllama

from langchain_openai import ChatOpenAI
from browser_use import ActionResult, Agent, Controller
from browser_use.browser.browser import Browser, BrowserConfig

# Load environment variables (not strictly needed without API keys)
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set logger level to DEBUG

# Remove existing handlers (if any)
logger.handlers = []

# Create a file handler
file_handler = logging.FileHandler("debug.log")
file_handler.setLevel(logging.DEBUG)  # Set handler level to DEBUG

# Create a formatter and add it to the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(file_handler)

# Test logging
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
controller = Controller()
api_key = os.getenv('DEEPSEEK_API_KEY', '')
# Path to your CV (optional)
CV = Path.cwd() / 'cv_04_24.pdf'
if not CV.exists():
    logger.warning(f"CV file not found at {CV}. Proceeding without CV context.")

# Job model for storing extracted data
class Job(BaseModel):
    title: str
    link: str
    company: str
    fit_score: float
    location: Optional[str] = None
    salary: Optional[str] = None

# Action to save jobs to CSV
@controller.action('Save jobs to file - with a score how well it fits to my profile', param_model=Job)
def save_jobs(job: Job):
    with open('jobs.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if file is new
        if f.tell() == 0:
            writer.writerow(["Company", "Title", "Link", "Salary", "Location", "Fit Score"])
        
        # Write job details in the desired format
        writer.writerow([job.company])  # Write company name
        writer.writerow(["\t", job.title, job.link])  # Write title, link, salary with a tab space
        writer.writerow(["\t Salary=", job.salary])  # Write salary with a tab space
        writer.writerow(["\t", job.location, f"fitscore={job.fit_score}"])  # Write location and fit score with a tab space
        writer.writerow(["\n\n"])  # Add an empty row for spacing between entries

    return 'Saved job to file'
# Action to read CV for context (optional)
@controller.action('Read my cv for context')
def read_cv():
    if not CV.exists():
        return ActionResult(error="CV file not found")
    pdf = PdfReader(CV)
    text = ''
    for page in pdf.pages:
        text += page.extract_text() or ''
    logger.info(f'Read CV with {len(text)} characters')
    return ActionResult(extracted_content=text, include_in_memory=True)

# Browser configuration
browser = Browser(
    config=BrowserConfig(
        chrome_instance_path='C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',  # Adjust for your system
        disable_security=True,
    )
)

# Main async function
async def main():
    # Define the task for SEEK
    ground_task = (
        "You are a professional job finder. "
        "1. Go to https://www.seek.com.au/ "
        "2. In the search bar, enter 'AI Engineer' "
        "3. Set the location filter to 'All Australia' "
        "4. Set Work Type to 'Part Time' and 'Cont ract/Temp' and 'Casual/Vacation' "
        "5. search for jobs."
        "6. For each job listing on the first page:\n"
        "   a. Click on the job title to open its detailed description, which appears as a pop-up on the right-hand side of the screen\n"
        "   b. Scroll through the entire pop-up description to ensure all details are visible\n"
        "   c. Extract the following details from the pop-up: job title, company name, job link (URL), salary (if available), location, and full job description text\n"
        "   d. Assign a fit score (0-1) based on relevance to software development \n"
        "   e. Save the extracted details to a file using the save_jobs action, including all fields (title, company, link, salary, location, fit_score, and description)\n"
        "7. Process all job listings on the first page as follows:\n"
        "   a. Create a list to keep track of processed job URLs to avoid duplicates\n"
        "   b. Open 5 new browser tabs to process jobs in parallel\n"
        "   c. For each of the first 5 unprocessed job listings, assign one to each tab and execute Step 6 in that tab\n"
        "   d. Wait until all 5 tabs complete Step 6, then close those tabs\n"
        "   e. If there are more unprocessed jobs, open another 5 tabs and repeat steps 7c and 7d until all jobs on the first page are processed\n"
        "   f. If fewer than 5 jobs remain, process them in parallel using the available number of tabs\n"
        "8. If any step fails (e.g., a job doesn’t open or details can’t be extracted), log the error and move to the next job\n"
        #"11. Go to the next page and repeat steps 5-10 for the first 4 pages"
        #"8. Go to the next page and repeat steps 5-7 for the first 5 pages"
    )

    # LLM setup with Ollama
    llm=ChatOpenAI(
			base_url='https://api.deepseek.com/v1',
			model='deepseek-chat',
			api_key=SecretStr(api_key),
		)
    #llm=ChatOllama(
     #       model="qwen2.5:7b",
    #        num_ctx=32000,
    #    )

    # Create and run the agent
    agent = Agent(
        task=ground_task,
        llm=llm,
        controller=controller,
        browser=browser,
        use_vision=False  # Vision may not work with qwen2.5; set to False if issues arise
        
    )
    
    await agent.run()

if __name__ == "__main__":
    #os.environ["ANONYMIZED_TELEMETRY"] = "false"
    #os.environ["OLLAMA_HOST"] = "http://localhost:11434"
    asyncio.run(main())