import logging
import json
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from typing import Dict, Optional
# Import updated models including TaskType
from models import InitialTopic, UserCommand, Task, TaskType, JobStatus, StatusUpdate
from websocket_manager import ConnectionManager
from task_manager import TaskManager
from orchestrator import Orchestrator
# No need to import agents directly in main.py

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Initialize Core Components ---
app = FastAPI(title="Multi-Agent Research Backend - v2 (LLM Planner)")
connection_manager = ConnectionManager()
task_manager = TaskManager(connection_manager=connection_manager)
orchestrator = Orchestrator(task_manager=task_manager)
task_manager.set_orchestrator(orchestrator) # Link back


# --- HTML for WebSocket Testing (Update JS) ---
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Research Agent Test (LLM Planner)</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            /* Keep styles from previous version */
             body { font-family: sans-serif; display: flex; gap: 20px; padding: 10px;}
            #controls { width: 350px; display: flex; flex-direction: column; gap: 15px; border-right: 1px solid #ccc; padding-right: 20px;}
            #updates { flex-grow: 1; display: flex; flex-direction: column;}
            #messages { flex-basis: 40%; max-height: 40vh; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; list-style: none;}
            #messages li { margin-bottom: 5px; padding: 5px; border-radius: 3px; border: 1px solid #ddd; font-size: 0.9em;}
            #report-output { flex-basis: 60%; border: 1px solid #aaa; padding: 15px; background-color: #f9f9f9; overflow-y: auto; }
            #report-output h1, #report-output h2, #report-output h3 { margin-top: 1em; margin-bottom: 0.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em;}
            #report-output p { line-height: 1.6; }
            #report-output code { background-color: #eee; padding: 2px 4px; border-radius: 3px; font-size: 0.9em;}
            #report-output pre { background-color: #eee; padding: 10px; overflow-x: auto;}
            #report-output pre code { display: block; padding: 0; background: none;}
            #report-output blockquote { border-left: 3px solid #ccc; padding-left: 10px; margin-left: 0; color: #555; }
            .task-params { font-size: 0.8em; color: #555; margin-left: 15px; }
            /* Status/Type Styles */
            .status-PENDING { background-color: #eee; }
            .status-RUNNING { background-color: #e0f7fa; border-left: 3px solid #00bcd4; }
            .status-COMPLETED { background-color: #e8f5e9; border-left: 3px solid #4caf50; }
            .status-ERROR { background-color: #ffebee; border-left: 3px solid #f44336; font-weight: bold; }
            .status-SKIPPED { background-color: #fffde7; border-left: 3px solid #ffeb3b; }
            .type-job_status { background-color: #e1f5fe; border-left: 3px solid #0288d1; font-weight: bold; margin-top: 10px;}
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
        <div id="controls">
            <h2>Initiate Research:</h2>
            <form id="research-form" action="" onsubmit="startResearch(event)">
                <label>Topic/Query: <textarea id="topicInput" rows="3" style="width: 95%;">Explain the potential impact of AI on software development jobs.</textarea></label>
                <button type="submit" id="start-button">Start Research</button>
            </form>

            <h2>Send Command:</h2>
            <form action="" onsubmit="sendCommand(event)">
                <label>Command: <input type="text" id="commandInput" autocomplete="off" value="skip" list="commands"/></label>
                <datalist id="commands"><option value="skip"><option value="resume"></datalist><br>
                <label>Task ID: <input type="text" id="taskIdInput" autocomplete="off" value="" placeholder="Task ID for skip" style="width: 80%; margin-bottom: 5px;"/></label><br>
                 <label>Job ID: <input type="text" id="jobIdInput" autocomplete="off" value="" placeholder="Job ID for resume" style="width: 80%;"/></label><br>
                <button type="submit">Send Command</button>
            </form>

             <h2>Live Updates:</h2>
             <ul id='messages'></ul>
        </div>

        <div id="updates">
             <h2>Final Report:</h2>
             <div id="report-output">
                 <p>Report will appear here once generated...</p>
             </div>
        </div>


        <script>
            const ws = new WebSocket(`ws://${location.host}/ws/frontend_client_${Date.now()}`); // Unique client ID
            const messagesList = document.getElementById('messages');
            const reportOutputDiv = document.getElementById('report-output');
            const startButton = document.getElementById('start-button');
            const topicInput = document.getElementById('topicInput');
            const jobIdInput = document.getElementById('jobIdInput');
            const taskIdInput = document.getElementById('taskIdInput');

            let currentJobId = null; // Track the current job

            ws.onopen = function(event) { addMessage("WebSocket Connected.", "system"); };
            ws.onerror = function(event) { addMessage("WebSocket Error.", "error"); console.error("WebSocket Error: ", event); };
            ws.onclose = function(event) { addMessage("WebSocket Closed.", "warning"); console.log("WebSocket Closed:", event); };

            ws.onmessage = function(event) {
                let data;
                try {
                    data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    addMessage("Received non-JSON: " + event.data, "warning");
                     console.warn("Non-JSON message:", event.data);
                }
            };

             function handleMessage(data) {
                console.log("Received message:", data); // Log all messages
                let message = document.createElement('li');
                let content = '';

                // Update current Job ID input if relevant
                if (data.job_id && !jobIdInput.value) {
                    jobIdInput.value = data.job_id;
                    currentJobId = data.job_id;
                }

                switch (data.type) {
                    case 'final_report':
                        addMessage(`Received final report for Job ${data.job_id}. Displaying.`, "info");
                        try {
                            reportOutputDiv.innerHTML = `<h2>Report for Job: ${data.job_id}</h2>` + marked.parse(data.report_markdown);
                        } catch(e) {
                            console.error("Error parsing Markdown:", e);
                            reportOutputDiv.innerHTML = `<h2>Report for Job: ${data.job_id} (Raw Markdown - Parsing Error)</h2><pre>${escapeHtml(data.report_markdown)}</pre>`;
                        }
                        // Re-enable start button when report is done
                        startButton.disabled = false;
                        startButton.textContent = "Start Research";
                        break;

                    case 'task_status': // Updated task status message
                        message.classList.add(`status-${data.status}`);
                        // --- Display Task Type ---
                        let taskType = data.detail?.match(/\(([^)]+)\)/)?.[1] || 'UNKNOWN'; // Extract type from detail if possible
                         if (data.detail?.includes("created for job")) taskType = data.detail.split('(')[1].split(')')[0]; // More reliable way?
                        // TODO: Backend should ideally send task_type in StatusUpdate model
                        content = `[JOB ${data.job_id || 'N/A'}] [TASK ${data.task_id}] <b>${data.status}</b> - ${data.detail || ''}`;
                        message.title = `Click to copy Task ID: ${data.task_id}`;
                        message.style.cursor = 'pointer';
                        message.onclick = () => { copyToClipboard(data.task_id, 'Task'); };
                        messagesList.insertBefore(message, messagesList.firstChild);
                        break; // Don't fall through

                    case 'job_status':
                        message.classList.add('type-job_status');
                        content = `[JOB ${data.job_id}] Status: <b>${data.status}</b> - ${data.detail}`;
                         messagesList.insertBefore(message, messagesList.firstChild);
                         // Re-enable button if job completes or fails
                         if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                              startButton.disabled = false;
                              startButton.textContent = "Start Research";
                         }
                        break;

                    case 'job_results_summary':
                        message.classList.add('type-job_results_summary');
                        // ... (summary display logic as before) ...
                        content = `<b>[JOB ${data.job_id}] Research Phase Summary:</b><br>...`; // Keep concise
                        messagesList.insertBefore(message, messagesList.firstChild);
                        break;

                    case 'job_error': // Handle specific job error messages from backend
                         content = `[JOB ERROR] ${data.detail || 'Unknown error'}`;
                         message.classList.add("error");
                         messagesList.insertBefore(message, messagesList.firstChild);
                          startButton.disabled = false; // Re-enable button on planning error etc.
                          startButton.textContent = "Start Research";
                         break;

                    case 'initial_state': // Assuming backend doesn't send this anymore, but handle defensively
                         addMessage(`Received initial state with ${data.tasks?.length || 0} tasks.`, "info");
                         break;

                    default: // Handle generic errors/warnings from backend
                        if (data.error) {
                             content = `[ERROR] ${data.error}`;
                             message.classList.add("error");
                        } else if (data.warning) {
                             content = `[WARNING] ${data.warning}`;
                             message.classList.add("warning");
                        } else {
                            content = "Received unhandled message type: " + (data.type || 'Unknown');
                            message.classList.add("info");
                             console.log("Unhandled message data:", data);
                        }
                         messagesList.insertBefore(message, messagesList.firstChild);
                }

            }

            // --- Helper Functions (addMessage, copyToClipboard, escapeHtml - keep as before) ---
            function addMessage(text, type = "info") { /* ... */ }
            function copyToClipboard(text, type) { /* ... */ }
            function escapeHtml(unsafe) { /* ... */ }

            // --- Updated sendCommand ---
            function sendCommand(event) {
                event.preventDefault();
                const command = document.getElementById("commandInput").value;
                const taskId = document.getElementById("taskIdInput").value;
                const jobId = document.getElementById("jobIdInput").value || currentJobId; // Use current job if not specified

                if (!jobId && command === 'resume') {
                    alert("Job ID is required to resume a job."); return;
                }
                 if (!taskId && command === 'skip') {
                    alert("Task ID is required to skip a task."); return;
                }

                const commandMsg = {
                    command: command,
                    task_id: taskId || null, // Send null if empty
                    job_id: jobId || null,   // Send null if empty
                    payload: {}
                };
                console.log("Sending command:", commandMsg);
                ws.send(JSON.stringify(commandMsg));
            }

            // --- Updated startResearch ---
            async function startResearch(event) {
                event.preventDefault();
                const topic = topicInput.value;
                if (!topic) { alert("Please enter a research topic/query."); return; }

                // Disable button, clear old report
                startButton.disabled = true;
                startButton.textContent = "Processing...";
                reportOutputDiv.innerHTML = "<p>Generating new report...</p>";
                messagesList.innerHTML = ""; // Clear old status messages
                currentJobId = null; // Reset current job ID
                jobIdInput.value = "";
                taskIdInput.value = "";


                try {
                    // --- Use the new endpoint ---
                    const response = await fetch('/start_job', { // <-- Endpoint changed
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', },
                        body: JSON.stringify({ query: topic }) // <-- Parameter name changed
                    });
                    const result = await response.json(); // Expecting {"message": "...", "job_id": "..."}
                    if (response.ok && result.job_id) {
                        console.log("Research job started:", result);
                        currentJobId = result.job_id;
                        jobIdInput.value = currentJobId; // Pre-fill Job ID input
                        addMessage(`Research job ${result.job_id} initiated for topic: ${topic}`, "info");
                    } else {
                        // Handle errors reported by the backend API call itself
                        const errorDetail = result.detail || response.statusText || 'Unknown error starting job.';
                        console.error("Error starting research job:", errorDetail);
                        addMessage(`Error starting research: ${errorDetail}`, "error");
                        alert(`Error starting research: ${errorDetail}`);
                        startButton.disabled = false; // Re-enable button on immediate failure
                        startButton.textContent = "Start Research";
                    }
                } catch (error) {
                    // Handle network errors etc.
                    console.error("Failed network request to start research job:", error);
                    addMessage("Failed to send start research request (network error).", "error");
                    alert("Failed to send start research request.");
                    startButton.disabled = false; // Re-enable button on network failure
                    startButton.textContent = "Start Research";
                }
            }
        </script>
    </body>
</html>
"""

# --- UPDATED /start_research Endpoint ---
@app.post("/start_job", status_code=status.HTTP_202_ACCEPTED) # Renamed endpoint
async def start_new_job(payload: Dict[str, str]): # Expect generic dict for query now
    """
    Initiates a new research job by calling the Planning Agent.
    """
    user_query = payload.get("query")
    if not user_query:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'query' field in request body.")

    logger.info(f"Received job request for query: {user_query}")
    try:
        # Call orchestrator to handle planning and job start
        job_id = await orchestrator.start_job(user_query=user_query)
        return {"message": "Research job initiated successfully.", "job_id": job_id}

    except (ValueError, RuntimeError) as e: # Catch planning or validation errors
         logger.error(f"Failed to plan or start job for query '{user_query}': {e}", exc_info=True)
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, # 400 might be appropriate if planning fails due to query
             detail=f"Failed to initiate job: {e}"
         )
    except Exception as e:
        logger.exception(f"Unexpected error starting job for query {user_query}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}"
        )


# --- Keep WebSocket endpoint and other parts as before ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # ... (WebSocket logic remains the same, handling connections and commands) ...
    await connection_manager.connect(websocket)
    # Send current task list upon connection? Maybe not useful anymore if jobs start fresh
    # initial_tasks = task_manager.get_all_tasks() # Might list old jobs
    # await connection_manager.send_personal_message(json.dumps({"type": "initial_state", "tasks": [t.dict() for t in initial_tasks]}), websocket)

    # Send status of any *currently* active jobs
    active_job_statuses = {job_id: status.value for job_id, status in orchestrator.active_jobs.items()}
    await connection_manager.send_personal_message(json.dumps({"type": "active_jobs", "jobs": active_job_statuses}), websocket)


    try:
        while True:
            data = await websocket.receive_text()
            # logger.info(f"Received message from {client_id}: {data}") # Already logged elsewhere usually
            try:
                command_data = json.loads(data)
                await task_manager.handle_user_command(command_data)
            except json.JSONDecodeError:
                 logger.warning(f"WS {client_id}: Received non-JSON message: {data}")
                 await connection_manager.send_personal_message(json.dumps({"error": "Invalid JSON"}), websocket)
            except Exception as e:
                 logger.error(f"WS {client_id}: Error processing command: {e}", exc_info=True)
                 await connection_manager.send_personal_message(json.dumps({"error": f"Error processing command: {e}"}), websocket)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Client #{client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@app.get("/")
async def get():
    return HTMLResponse(html)

# Graceful shutdown (optional but recommended)
# @app.on_event("shutdown") ...

# --- Run the app ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for Multi-Agent Research Backend v2...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Use reload=True for dev