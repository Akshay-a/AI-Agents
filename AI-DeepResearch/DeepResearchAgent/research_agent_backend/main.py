import logging
import json
import asyncio # Import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status
from fastapi.responses import HTMLResponse

from models import InitialTopic, UserCommand, Task # Import Task
from websocket_manager import ConnectionManager
from task_manager import TaskManager
from orchestrator import Orchestrator # Import Orchestrator
from persistence import save_tasks_to_md # Import persistence function

# Configure logging (keep as before)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Research Backend")

# --- Instantiate Managers ---
connection_manager = ConnectionManager()
# Instantiate orchestrator first (or handle dependency injection better)
# Pass None for orchestrator initially if TM needs it first
task_manager = TaskManager(connection_manager=connection_manager)
orchestrator = Orchestrator(task_manager=task_manager)
# Now set the orchestrator reference in the task manager
task_manager.set_orchestrator(orchestrator)


# --- Simple HTML for WebSocket Testing (Update slightly) ---
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Research Agent Test</title>
        <style>
            body { font-family: sans-serif; }
            #messages li { margin-bottom: 5px; padding: 3px; border-radius: 3px; }
            .status-PENDING { background-color: #eee; }
            .status-RUNNING { background-color: #e0f7fa; }
            .status-COMPLETED { background-color: #e8f5e9; }
            .status-ERROR { background-color: #ffebee; font-weight: bold; }
            .status-SKIPPED { background-color: #fffde7; }
            .type-job_status { background-color: #e1f5fe; border-left: 3px solid #0288d1; }
        </style>
    </head>
    <body>
        <h1>Research Agent WebSocket Test</h1>
        <h2>Live Updates (Tasks & Job Status):</h2>
        <ul id='messages'>
        </ul>
        <hr>
        <h2>Send Command:</h2>
        <form action="" onsubmit="sendCommand(event)">
            <label>Command: <input type="text" id="commandInput" autocomplete="off" value="skip"/></label><br>
            <label>Task ID: <input type="text" id="taskIdInput" autocomplete="off" value="" placeholder="Task ID to skip/resume"/></label><br>
            <label>Payload (JSON): <input type="text" id="payloadInput" autocomplete="off" value="{}"/></label><br>
            <button>Send Command</button>
            <button type="button" onclick="sendResumeCommand()">Resume Job (using Task ID)</button>
        </form>
         <hr>
         <h2>Initiate Research (POST request needed)</h2>
         <p>Use tool like curl or Postman to POST to /start_research with {"topic": "your_topic"}</p>

        <script>
            var ws = new WebSocket(`ws://${location.host}/ws/test_client`);
            var messages = document.getElementById('messages');

            ws.onopen = function(event) {
                var li = document.createElement('li');
                li.textContent = "WebSocket Connected.";
                li.style.color = "green";
                messages.appendChild(li);
            };

            ws.onmessage = function(event) {
                var message = document.createElement('li');
                var data;
                try {
                    data = JSON.parse(event.data);
                    message.textContent = event.data; // Display raw JSON

                    // Add specific styling based on message type or status
                    if (data.type === 'job_status') {
                        message.classList.add('type-job_status');
                        message.textContent = `[JOB ${data.job_id}] Status: ${data.status} - ${data.detail}`;
                    } else if (data.task_id && data.status) { // Assume task update
                         message.classList.add(`status-${data.status}`);
                         message.textContent = `[TASK ${data.task_id}] Status: ${data.status} - ${data.detail || ''} (Job: ${data.job_id || 'N/A'})`;
                    } else if (data.type === 'initial_state') {
                        message.textContent = `Received initial state with ${data.tasks.length} tasks.`;
                         // Optionally list initial tasks
                         data.tasks.forEach(task => {
                             var taskLi = document.createElement('li');
                             taskLi.classList.add(`status-${task.status}`);
                             taskLi.textContent = `[INITIAL TASK ${task.id}] Status: ${task.status} - ${task.description} (Job: ${task.job_id || 'N/A'})`;
                             messages.appendChild(taskLi);
                         });
                         return; // Don't add the 'initial_state' meta message itself
                    }


                } catch (e) {
                    message.textContent = event.data; // Display as raw text if not JSON
                }
                // Prepend new messages
                messages.insertBefore(message, messages.firstChild);
            };

            ws.onerror = function(event) {
                 var li = document.createElement('li');
                 li.textContent = "WebSocket Error.";
                 li.style.color = "red";
                 messages.appendChild(li);
                 console.error("WebSocket Error: ", event);
            };

             ws.onclose = function(event) {
                 var li = document.createElement('li');
                 li.textContent = "WebSocket Closed.";
                 li.style.color = "orange";
                 messages.appendChild(li);
                 console.log("WebSocket Closed:", event);
            };

            function sendCommand(event) {
                var command = document.getElementById("commandInput").value;
                var taskId = document.getElementById("taskIdInput").value;
                var payloadStr = document.getElementById("payloadInput").value;
                var payload;
                if (!taskId) { alert("Task ID is required for skip/resume"); return; }
                try { payload = JSON.parse(payloadStr); } catch (e) { alert("Invalid JSON payload"); return; }

                var commandMsg = { command: command, task_id: taskId, payload: payload };
                console.log("Sending command:", commandMsg);
                ws.send(JSON.stringify(commandMsg));
                if(event) event.preventDefault(); // Prevent form submission if called from form
            }

            function sendResumeCommand() {
                 // Simplified: Use the same Task ID input field to identify the job to resume
                 document.getElementById("commandInput").value = "resume";
                 sendCommand(null); // Pass null event
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

# --- WebSocket Endpoint (mostly unchanged, relies on managers) ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket)
    # Send current task list upon connection
    initial_tasks = task_manager.get_all_tasks()
    await connection_manager.send_personal_message(
        json.dumps({"type": "initial_state", "tasks": [t.dict() for t in initial_tasks]}), # Use .dict() for pydantic v1
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

            # Keep error handling for JSON, Validation etc.
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
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


# --- REST API Endpoint (Updated) ---
@app.post("/start_research", status_code=status.HTTP_202_ACCEPTED)
async def start_research(payload: InitialTopic, request: Request):
    """
    Initiates the research process by creating the initial 'Plan' task
    and starting the orchestrator's research flow.
    """
    logger.info(f"Received research request for topic: {payload.topic}")
    try:
        # 1. Create only the initial planning task
        # The job_id will be the ID of this first task.
        plan_task = await task_manager.add_task(f"Plan research for: {payload.topic}", job_id=None) # Job ID set below
        plan_task.job_id = plan_task.id # Assign the task's own ID as the Job ID
        task_manager.tasks[plan_task.id] = plan_task # Update task in manager with job_id
        logger.info(f"Assigned Job ID {plan_task.job_id} based on initial task.")
        save_tasks_to_md(task_manager.tasks) # Save updated task with job_id

        # 2. Start the orchestrator's flow for this job in the background
        # Use asyncio.create_task to run it concurrently
        # await orchestrator.start_job(initial_task_id=plan_task.id, topic=payload.topic)
        # Use request.app.state for robust background task handling if needed, or just create_task for simplicity now
        asyncio.create_task(orchestrator.start_job(initial_task_id=plan_task.id, topic=payload.topic))


        logger.info(f"Orchestrator job initiated for Job ID: {plan_task.id}")

        return {"message": "Research job initiated", "job_id": plan_task.id, "initial_task_id": plan_task.id}

    except Exception as e:
        logger.exception(f"Error starting research for topic {payload.topic}: {e}")
        await connection_manager.broadcast(json.dumps({"error": f"Failed to initiate research process: {str(e)}"}))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate research process: {str(e)}"
        )
@app.post("/shutdown")
async def shutdown(request: Request):
    uvicorn.server.UvicornServer.request_handler = request.scope["asgi"].send
    asyncio.get_event_loop().callsoon(uvicorn.server.UvicornServer.stop)
    return {"message": "Shutting down server..."}

# --- Run the app (keep as before) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)