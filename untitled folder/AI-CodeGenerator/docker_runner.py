import docker
import tempfile
import os
import logging
import time
import config
from utils import parse_imports # Import the new parser

logger = logging.getLogger(__name__)

def execute_code(code_string: str) -> tuple[str | None, str | None, int | None]:
    """
    Executes Python code securely in a Docker container, handling dependencies.

    Args:
        code_string: The Python code to execute.

    Returns:
        A tuple containing (stdout, stderr, exit_code).
        Returns (None, error_message, -1) on Docker setup/runtime errors.
    """
    client = None
    container = None
    tmpdir_obj = None # Use the object to ensure cleanup

    try:
        logger.info("Initializing Docker client...")
        client = docker.from_env()
        client.ping()
        logger.info("Docker client initialized successfully.")

        # --- Dependency Handling ---
        external_packages = parse_imports(code_string)
        pip_install_command = ""
        if external_packages:
            package_list = " ".join(list(external_packages))
            # Command to install packages within the container's virtual env
            pip_install_command = f"pip install --disable-pip-version-check --no-cache-dir {package_list}"
            logger.info(f"Will attempt to install packages in container: {package_list}")
        else:
            logger.info("No external packages detected; skipping pip install.")
        # --- End Dependency Handling ---


        # Ensure the image exists locally or pull it
        try:
            client.images.get(config.DOCKER_IMAGE)
            logger.info(f"Docker image '{config.DOCKER_IMAGE}' found locally.")
        except docker.errors.ImageNotFound:
            logger.warning(f"Docker image '{config.DOCKER_IMAGE}' not found. Pulling...")
            try:
                client.images.pull(config.DOCKER_IMAGE)
                logger.info("Docker image pulled successfully.")
            except docker.errors.APIError as e:
                logger.error(f"Failed to pull Docker image '{config.DOCKER_IMAGE}': {e}", exc_info=True)
                return None, f"Failed to pull Docker image: {e}", -1

        # Create a temporary directory
        tmpdir_obj = tempfile.TemporaryDirectory()
        tmpdir = tmpdir_obj.name # Get the path string
        script_filename = "agent_script.py"
        script_path_host = os.path.join(tmpdir, script_filename)
        script_path_container = f"/app/{script_filename}"
        working_dir_container = "/app"

        logger.info(f"Saving code to temporary file: {script_path_host}")
        with open(script_path_host, "w", encoding="utf-8") as f:
            f.write(code_string)

        # --- Construct Execution Command ---
        # Use sh -c to run multiple commands. Use '. .venv/bin/activate' for activation.
        # Always create venv for consistency, even if no packages needed? Decision: Yes, simpler logic flow.
        # Use && to stop if a command fails (e.g., venv creation or pip install)
        venv_path = ".venv_agent" # Name for the virtual environment directory inside container
        commands = [
            f"cd {working_dir_container}",
            f"python -m venv {venv_path}", # Create venv
            f". {venv_path}/bin/activate" # Activate venv (using '.')
        ]
        additionalTimeout=0
        if pip_install_command:
            commands.append(pip_install_command) # Install packages if needed
            additionalTimeout = 120

        commands.append(f"python {script_filename}") # Execute the script

        full_command = " && ".join(commands)
        shell_command = ["sh", "-c", full_command]

        logger.info(f"Running command in Docker: {' '.join(shell_command)}")
        # --- End Construct Execution Command ---

        start_time = time.time()

        container = client.containers.run(
            config.DOCKER_IMAGE,
            command=shell_command, # Use the shell command list
            volumes={tmpdir: {'bind': working_dir_container, 'mode': 'rw'}},
            working_dir=working_dir_container,
            detach=True,
            network_mode='bridge', # Keep default 'bridge' to allow pip downloads
            # Consider resource limits
            # mem_limit="512m", # Increased slightly for pip install
            # cpus=1.0,
        )

        # Wait for container completion with timeout
        try:
            result = container.wait(timeout=config.DOCKER_TIMEOUT_SECONDS+additionalTimeout)
            exit_code = result.get('StatusCode', -1)
            stdout_bytes = container.logs(stdout=True, stderr=False)
            stderr_bytes = container.logs(stdout=False, stderr=True)
            end_time = time.time()
            logger.info(f"Container finished in {end_time - start_time:.2f}s with exit code {exit_code}.")

        except Exception as e: # Catches timeout (requests.exceptions.ReadTimeout) etc.
            logger.error(f"Container execution failed or timed out ({config.DOCKER_TIMEOUT_SECONDS}s): {e}", exc_info=True)
            stdout_bytes, stderr_bytes = b"", b"" # Clear logs on timeout before trying to retrieve again
            try:
                stdout_bytes = container.logs(stdout=True, stderr=False, tail=100)
                stderr_bytes = container.logs(stdout=False, stderr=True, tail=100)
                logger.info("Retrieved partial logs after timeout/error.")
            except Exception as log_err:
                 logger.error(f"Could not retrieve logs after timeout/error: {log_err}")

            # Construct meaningful error for timeout/failure
            stderr_msg = f"Execution timed out after {config.DOCKER_TIMEOUT_SECONDS}s or failed.\nError during wait: {e}\n--- Potential container stderr (last 100 lines) ---\n"
            if stderr_bytes:
                 stderr_msg += stderr_bytes.decode('utf-8', errors='ignore')
            else:
                 stderr_msg += "<No stderr captured>"

            # Ensure container is stopped
            try:
                logger.warning("Stopping potentially hung container...")
                container.stop(timeout=5)
            except Exception as stop_err:
                logger.error(f"Failed to stop container after error: {stop_err}")

            return (stdout_bytes.decode('utf-8', errors='ignore'), stderr_msg, -1)

        finally:
            # Ensure container is always removed
            if container:
                try:
                    logger.debug(f"Removing container {container.id[:12]}...")
                    container.remove(force=True)
                    logger.debug("Container removed.")
                except docker.errors.NotFound:
                    logger.debug("Container already removed.")
                except Exception as rm_err:
                    logger.error(f"Error removing container {container.id[:12]}: {rm_err}", exc_info=True)

        stdout = stdout_bytes.decode('utf-8', errors='ignore')
        stderr = stderr_bytes.decode('utf-8', errors='ignore')

        # Log stderr clearly, as it might contain pip output/errors too
        if stderr:
            logger.warning(f"Execution STDERR (may include pip output):\n{stderr}")
        else:
            logger.debug("Execution STDERR: <Empty>")
        logger.debug(f"Execution STDOUT:\n{stdout}")

        return stdout, stderr, exit_code

    except docker.errors.DockerException as e:
        logger.critical(f"Docker error: {e}. Is Docker running?", exc_info=True)
        return None, f"Docker error: {e}. Ensure Docker is running.", -1
    except Exception as e:
        logger.critical(f"Unexpected error during Docker execution setup: {e}", exc_info=True)
        return None, f"Unexpected setup error: {e}", -1
    finally:
        if tmpdir_obj:
            try:
                tmpdir_obj.cleanup()
                logger.debug("Temporary directory cleaned up.")
            except Exception as e:
                logger.warning(f"Could not clean up temporary directory {tmpdir}: {e}")
        if client:
            try:
                client.close()
            except Exception:
                pass