
import logging
import json
import asyncio
import os # Import os for environment variable check
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv # Import dotenv

from models import InitialTopic, UserCommand, Task
from websocket_manager import ConnectionManager
from task_manager import TaskManager
from orchestrator import Orchestrator
from persistence import save_tasks_to_md

load_dotenv() 

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
if not SERPAPI_API_KEY:
    logging.warning("SERPAPI_API_KEY environment variable not set. Search functionality will fail.")
    raise ValueError("SERPAPI_API_KEY environment variable must be set.")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Research Backend")


connection_manager = ConnectionManager()

task_manager = TaskManager(connection_manager=connection_manager)

orchestrator = Orchestrator(task_manager=task_manager)
# Link Orchestrator back to TaskManager for command handling
task_manager.set_orchestrator(orchestrator)

# --- HTML for WebSocket Testing (Keep as before) ---
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Research Agent Test</title>
        <style>
            body { font-family: sans-serif; }
            #messages li { margin-bottom: 5px; padding: 5px; border-radius: 3px; list-style: none; border: 1px solid #ddd;}
            .status-PENDING { background-color: #eee; }
            .status-RUNNING { background-color: #e0f7fa; border-left: 3px solid #00bcd4; }
            .status-COMPLETED { background-color: #e8f5e9; border-left: 3px solid #4caf50; }
            .status-ERROR { background-color: #ffebee; border-left: 3px solid #f44336; font-weight: bold; }
            .status-SKIPPED { background-color: #fffde7; border-left: 3px solid #ffeb3b; }
            .type-job_status { background-color: #e1f5fe; border-left: 3px solid #0288d1; font-weight: bold; margin-top: 10px;}
            /* --- NEW STYLE for Summary --- */
            .type-job_results_summary { background-color: #f3e5f5; border-left: 3px solid #8e24aa; margin-top: 10px; padding-bottom: 10px; }
            .type-job_results_summary ul { margin-top: 5px; margin-bottom: 0; padding-left: 20px; }
            .type-job_results_summary li { border: none; padding: 2px 0; margin: 0; font-size: 0.9em; }
            .info { color: #333; font-weight: normal; }
            .error { color: red; }
            .warning { color: orange; }
            .system { color: green; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>Research Agent WebSocket Test</h1>
        <h2>Live Updates (Job & Task Status):</h2>
        <ul id='messages'>
        </ul>
        <hr>
        <h2>Send Command:</h2>
        <form action="" onsubmit="sendCommand(event)">
            <label>Command: <input type="text" id="commandInput" autocomplete="off" value="skip" list="commands"/></label>
            <datalist id="commands"><option value="skip"><option value="resume"></datalist><br>
            <label>Task ID: <input type="text" id="taskIdInput" autocomplete="off" value="" placeholder="Task ID for skip/resume"/></label><br>
            <button>Send Command (Skip/Resume Task)</button>
        </form>
         <hr>
         <h2>Initiate Research:</h2>
         <form action="" onsubmit="startResearch(event)">
             <label>Topic: <input type="text" id="topicInput" autocomplete="off" value="Quantum Computing Basics"/></label>
             <button>Start Research</button>
         </form>

        <script>
            var ws = new WebSocket(`ws://${location.host}/ws/test_client`);
            var messages = document.getElementById('messages');

            ws.onopen = function(event) {
                addMessage("WebSocket Connected.", "system");
            };

            ws.onmessage = function(event) {
                var data;
                try {
                    data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    addMessage("Received non-JSON: " + event.data, "warning");
                }
            };

            ws.onerror = function(event) {
                 addMessage("WebSocket Error.", "error");
                 console.error("WebSocket Error: ", event);
            };

             ws.onclose = function(event) {
                 addMessage("WebSocket Closed.", "warning");
                 console.log("WebSocket Closed:", event);
            };

            function handleMessage(data) {
                var message = document.createElement('li');
                var content = '';

                if (data.type === 'job_status') {
                    message.classList.add('type-job_status');
                    content = `[JOB ${data.job_id}] Status: ${data.status} - ${data.detail}`;
                }
                // --- START: Handle Summary Message ---
                else if (data.type === 'job_results_summary') {
                    message.classList.add('type-job_results_summary');
                    content = `<b>[JOB ${data.job_id}] Research Phase Summary:</b><br>` +
                              `  Found <b>${data.unique_sources_found}</b> unique sources (analyzed ${data.sources_analyzed_count}, removed ${data.duplicates_removed} duplicates).`;
                    if (data.top_sources && data.top_sources.length > 0) {
                        content += "<br>  Top sources found:";
                        var sourceList = "<ul>";
                        data.top_sources.forEach(source => {
                            sourceList += `<li>${source.title || 'No Title'} (<a href="${source.url}" target="_blank" rel="noopener noreferrer">${source.url}</a>)</li>`;
                        });
                        sourceList += "</ul>";
                        content += sourceList;
                    }
                }
                // --- END: Handle Summary Message ---
                else if (data.task_id && data.status) { // Assume task update
                     message.classList.add(`status-${data.status}`);
                     let detailText = data.detail || '';
                     if (detailText.length > 150) detailText = detailText.substring(0, 150) + '...';
                     content = `[TASK ${data.task_id}] Status: <b>${data.status}</b> - ${detailText} (Job: ${data.job_id || 'N/A'})`;
                     message.title = `Click to copy Task ID: ${data.task_id}`;
                     message.style.cursor = 'pointer';
                     message.onclick = () => { copyToClipboard(data.task_id, 'Task'); };
                } else if (data.type === 'initial_state') {
                    addMessage(`Received initial state with ${data.tasks.length} tasks.`, "info");
                     data.tasks.forEach(task => {
                         var taskLi = document.createElement('li');
                         taskLi.classList.add(`status-${task.status}`);
                         let detailText = task.description || '';
                         if (detailText.length > 150) detailText = detailText.substring(0, 150) + '...';
                         taskLi.innerHTML = `[INITIAL TASK ${task.id}] Status: <b>${task.status}</b> - ${detailText} (Job: ${task.job_id || 'N/A'})`;
                         taskLi.title = `Click to copy Task ID: ${task.id}`;
                         taskLi.style.cursor = 'pointer';
                         taskLi.onclick = () => { copyToClipboard(task.id, 'Task'); };
                         messages.insertBefore(taskLi, messages.firstChild);
                     });
                     return; // Don't add the 'initial_state' meta message itself
                } else if (data.error) {
                     content = `[ERROR] ${data.error}`;
                     message.classList.add("error");
                } else if (data.warning) {
                     content = `[WARNING] ${data.warning}`;
                     message.classList.add("warning");
                } else {
                    content = "Received unknown message format: " + JSON.stringify(data);
                    message.classList.add("info");
                }

                message.innerHTML = content; // Use innerHTML to render bold tags, links etc.
                messages.insertBefore(message, messages.firstChild);
            }

            // Helper function to add simple text messages
            function addMessage(text, type = "info") {
                 var li = document.createElement('li');
                 li.textContent = text;
                 li.classList.add(type);
                 messages.insertBefore(li, messages.firstChild);
            }

            // Helper function for copying ID
            function copyToClipboard(text, type) {
                navigator.clipboard.writeText(text).then(() => {
                    console.log(`Copied ${type} ID: ${text}`);
                    document.getElementById('taskIdInput').value = text; // Populate input field
                }, (err) => {
                    console.error(`Failed to copy ${type} ID: `, err);
                    alert(`Failed to copy ${type} ID.`);
                });
            }

            function sendCommand(event) {
                // ... (keep sendCommand function exactly as it was) ...
                 var command = document.getElementById("commandInput").value;
                var taskId = document.getElementById("taskIdInput").value;
                if (!taskId && command !== 'resume_all') {
                     alert("Task ID is required for skip/resume specific task");
                     return;
                }
                var commandMsg = { command: command, task_id: taskId, payload: {} };
                console.log("Sending command:", commandMsg);
                ws.send(JSON.stringify(commandMsg));
                if(event) event.preventDefault();
            }

            async function startResearch(event) {
                // ... (keep startResearch function exactly as it was) ...
                event.preventDefault();
                var topic = document.getElementById('topicInput').value;
                if (!topic) { alert("Please enter a research topic."); return; }
                try {
                    const response = await fetch('/start_research', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', },
                        body: JSON.stringify({ topic: topic })
                    });
                    const result = await response.json();
                    if (response.ok) {
                        console.log("Research started:", result);
                        addMessage(`Research job ${result.job_id} initiated for topic: ${topic}`, "info");
                    } else {
                        addMessage(`Error starting research: ${result.detail || 'Unknown error'}`, "error");
                        alert(`Error starting research: ${result.detail || 'Unknown error'}`);
                    }
                } catch (error) {
                    console.error("Failed to send start research request:", error);
                    addMessage("Failed to send start research request.", "error");
                    alert("Failed to send start research request.");
                }
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

# --- WebSocket Endpoint (Keep as before) ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket)
    # Send current task list upon connection
    initial_tasks = task_manager.get_all_tasks()
    await connection_manager.send_personal_message(
        json.dumps({"type": "initial_state", "tasks": [t.dict() for t in initial_tasks]}),
        websocket
    )
    # Also send status of active jobs
    for job_id, status in orchestrator.active_jobs.items():
         await connection_manager.send_personal_message(
              json.dumps({"type": "job_status", "job_id": job_id, "status": status.value, "detail": f"Job currently {status.value}"}),
              websocket
         )

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")
            try:
                command_data = json.loads(data)
                # Pass command to task manager for handling
                await task_manager.handle_user_command(command_data)

            except json.JSONDecodeError:
                 logger.warning(f"Received non-JSON message: {data}")
                 await connection_manager.send_personal_message(json.dumps({"error": "Invalid JSON"}), websocket)
            except Exception as e: # Catch broader errors during command handling
                 logger.error(f"Error processing command from client {client_id}: {e}", exc_info=True)
                 await connection_manager.send_personal_message(json.dumps({"error": f"Internal server error processing command: {e}"}), websocket)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Client #{client_id} disconnected")
    except Exception as e:
        # Log other WebSocket errors
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        connection_manager.disconnect(websocket) # Ensure disconnect on error

# --- REST API Endpoint (Keep as before) ---
@app.post("/start_research", status_code=status.HTTP_202_ACCEPTED)
async def start_research(payload: InitialTopic, request: Request):
    logger.info(f"Received research request for topic: {payload.topic}")
    try:
        # Create initial planning task ( first task in the chain)
        plan_task = await task_manager.add_task(f"Plan research for: {payload.topic}", job_id=None)
        plan_task.job_id = plan_task.id # Assign task's own ID as Job ID
        task_manager.tasks[plan_task.id] = plan_task
        logger.info(f"Assigned Job ID {plan_task.job_id} based on initial task.")
        save_tasks_to_md(task_manager.tasks)

        # Start orchestrator job in the background
        asyncio.create_task(orchestrator.start_job(initial_task_id=plan_task.id, topic=payload.topic))
        logger.info(f"Orchestrator job initiated for Job ID: {plan_task.id}")

        return {"message": "Research job initiated", "job_id": plan_task.id, "initial_task_id": plan_task.id}

    except Exception as e:
        logger.exception(f"Error starting research for topic {payload.topic}: {e}")
        # Don't broadcast here, let the client handle the HTTP error
        # await connection_manager.broadcast(json.dumps({"error": f"Failed to initiate research process: {str(e)}"}))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate research process: {str(e)}"
        )

# --- Graceful Shutdown (Optional but Recommended) ---
#@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down server...")
    # Cancel active orchestrator jobs
    for job_id, job_task in list(orchestrator.job_tasks.items()): # Iterate over a copy
        if not job_task.done():
            job_task.cancel()
            logger.info(f"Cancelled job task {job_id}")
            try:
                await job_task # Wait briefly for cancellation to propagate
            except asyncio.CancelledError:
                logger.info(f"Job task {job_id} cancellation confirmed.")
            except Exception as e:
                 logger.error(f"Error during job task {job_id} cancellation: {e}")
    # Close WebSocket connections
    await connection_manager.shutdown()
    logger.info("Shutdown complete.")

# --- Run the app (keep as before, ensure reload=True for dev) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server...")
    # Consider reload=False for production
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
