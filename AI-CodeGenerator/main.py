import sys
import os
import logging
import config 
from utils import setup_logging, save_code_to_file
import llm_handler
import docker_runner

# Setup logging as early as possible
setup_logging()
logger = logging.getLogger(__name__)

def run_agent():
    """Main function to run the AI coding agent."""
    logger.info("--- Starting AI Code Generation Agent ---")

    # --- Pre-run Checks ---
    if not config.API_KEY:
        logger.critical("❌ GOOGLE_API_KEY not found.set it in .env or environment variables.")
        sys.exit(1)
    logger.info("✅ Google API Key found.")

    # Check Docker connection (basic check, more thorough check happens in docker_runner)
    try:
        import docker
        client = docker.from_env()
        client.ping()
        client.close()
        logger.info("✅ Docker daemon appears to be running.")
    except Exception as e:
        logger.critical(f"❌ Docker connection failed: {e}. Please ensure Docker is installed and running.")
        sys.exit(1)

    # Ensure output directory exists
    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        logger.info(f"Output directory ensured at: {config.OUTPUT_DIR}")
    except OSError as e:
        logger.critical(f"❌ Could not create output directory '{config.OUTPUT_DIR}': {e}")
        sys.exit(1)


    # --- Get Requirements ---
    try:
        requirements = input("▶ Enter the requirements for the Python code: ")
        if not requirements:
            logger.error("❌ Requirements cannot be empty.")
            sys.exit(1)
        logger.info(f"Received requirements: {requirements}")
    except EOFError:
         logger.error("\n❌ No input received (EOF). Exiting.")
         sys.exit(1)


    # --- Iteration Loop ---
    current_code = None
    last_error = ""
    success = False

    for iteration in range(config.MAX_ITERATIONS):
        logger.info(f"--- Iteration {iteration + 1}/{config.MAX_ITERATIONS} ---")

        # 1. Generate or Refine Code
        if iteration == 0:
            logger.info("Attempting to generate initial code...")
            current_code = llm_handler.generate_initial_code(requirements)
            if current_code:
                 save_code_to_file(current_code, config.INITIAL_CODE_FILENAME_TPL.format(iteration + 1))
            else:
                 logger.error("Failed to generate initial code from LLM.")
                 break # Cannot proceed without initial code
        else:
            if not current_code or not last_error:
                 logger.error("Cannot perform debugging iteration without previous code and error.")
                 break
            logger.info("Attempting to debug previous code...")
            corrected_code = llm_handler.debug_code(requirements, current_code, last_error)
            if corrected_code:
                current_code = corrected_code # Update code
                save_code_to_file(current_code, config.CORRECTED_CODE_FILENAME_TPL.format(iteration + 1))
            else:
                logger.error("LLM failed to provide corrected code. Retrying execution with previous code might be futile, but proceeding...")
                # Optionally: break here if LLM fails to debug? Depends on desired behavior.

        if not current_code:
            logger.error("No code available to execute for this iteration.")
            continue # Or break, depending on desired logic

        # 2. Execute Code
        logger.info(f"Executing code from iteration {iteration + 1} in Docker...")
        stdout, stderr, exit_code = docker_runner.execute_code(current_code)

        logger.info(f"Execution Result (Iteration {iteration + 1}):")
        logger.info(f"  Exit Code: {exit_code}")
        logger.info(f"  STDOUT:\n{stdout if stdout else '<No Output>'}")
        logger.info(f"  STDERR:\n{stderr if stderr else '<No Errors>'}")

        # 3. Evaluate Result & Decide Next Step
        # Simple success condition: exit code 0 AND empty stderr. Adjust if needed.
        if exit_code == 0 and not stderr:
            logger.info(f"✅ Code executed successfully in iteration {iteration + 1}!")
            final_filepath = save_code_to_file(current_code, config.FINAL_CODE_FILENAME)
            if final_filepath:
                 logger.info(f"Final working code saved to: {final_filepath}")
            else:
                 logger.error("Failed to save the final working code!")
            success = True
            break # Exit loop on success
        else:
            # Failure - Prepare for next iteration or final failure
            last_error = stderr if stderr else f"Script exited with non-zero code: {exit_code}"
            if iteration < config.MAX_ITERATIONS - 1:
                logger.warning(f"Code execution failed. Error:\n{last_error}")
                logger.info("Proceeding to next iteration for debugging...")
            else:
                logger.error(f"Code execution failed on the final iteration ({iteration + 1}).")
                logger.error(f"Last error message:\n{last_error}")

    # --- Final Status ---
    logger.info("--- Agent Run Finished ---")
    if success:
        logger.info("✅ Successfully generated and executed working code.")
    else:
        logger.error(f"❌ Failed to produce working code within {config.MAX_ITERATIONS} iterations.")
        logger.error("Check the 'output/' directory for logs and intermediate code files.")

    logger.info("--------------------------")


if __name__ == "__main__":
    run_agent()