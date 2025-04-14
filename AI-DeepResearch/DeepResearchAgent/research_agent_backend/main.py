import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status
from fastapi.responses import HTMLResponse # For simple testing
from pydantic import ValidationError

from models import InitialTopic, UserCommand
from websocket_manager import ConnectionManager
from task_manager import TaskManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Research Backend")

# --- Instantiate Managers ---
connection_manager = ConnectionManager()
task_manager = TaskManager(connection_manager=connection_manager)

# --- Simple HTML for WebSocket Testing ---
# In a real app, this would be your React frontend
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Research Agent Test</title>
    </head>
    <body>
        <h1>Research Agent WebSocket Test</h1>
        <h2>Status Updates:</h2>
        <ul id='messages'>
        </ul>
        <hr>
        <h2>Send Command:</h2>
        <form action="" onsubmit="sendCommand(event)">
            <label>Command: <input type="text" id="commandInput" autocomplete="off" value="skip"/></label><br>
            <label>Task ID: <input type="text" id="taskIdInput" autocomplete="off" value=""/></label><br>
            <label>Payload (JSON): <input type="text" id="payloadInput" autocomplete="off" value="{}"/></label><br>
            <button>Send Command</button>
        </form>
         <hr>
         <h2>Initiate Research (POST request needed)</h2>
         <p>Use tool like curl or Postman to POST to /start_research with {"topic": "your_topic"}</p>

        <script>
            var ws = new WebSocket(`ws://${location.host}/ws/test_client`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data);
                message.appendChild(content);
                messages.appendChild(message);
            };
            function sendCommand(event) {
                var command = document.getElementById("commandInput").value;
                var taskId = document.getElementById("taskIdInput").value;
                var payloadStr = document.getElementById("payloadInput").value;
                var payload;
                try {
                    payload = JSON.parse(payloadStr);
                } catch (e) {
                    alert("Invalid JSON payload");
                    return;
                }
                var commandMsg = { command: command, task_id: taskId, payload: payload };
                ws.send(JSON.stringify(commandMsg));
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

# --- WebSocket Endpoint ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket)
    # Send current task list upon connection
    initial_tasks = task_manager.get_all_tasks()
    await connection_manager.send_personal_message(json.dumps({"type": "initial_state", "tasks": [t.dict() for t in initial_tasks]}), websocket)

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")
            try:
                command_data = json.loads(data)
                # Basic validation before passing to task manager
                if isinstance(command_data, dict) and 'command' in command_data and 'task_id' in command_data:
                     await task_manager.handle_user_command(command_data)
                else:
                     logger.warning(f"Invalid command format received: {data}")
                     await connection_manager.send_personal_message(json.dumps({"error": "Invalid command format"}), websocket)

            except json.JSONDecodeError:
                 logger.warning(f"Received non-JSON message: {data}")
                 await connection_manager.send_personal_message(json.dumps({"error": "Invalid JSON"}), websocket)
            except ValidationError as e:
                 logger.warning(f"Command validation failed: {e}")
                 await connection_manager.send_personal_message(json.dumps({"error": f"Command validation failed: {e}"}), websocket)
            except Exception as e:
                 logger.error(f"Error processing command from client: {e}")
                 await connection_manager.send_personal_message(json.dumps({"error": "Internal server error processing command"}), websocket)


    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Client #{client_id} disconnected")
    except Exception as e:
        # Catch potential errors during receive or processing
        logger.error(f"WebSocket error for client {client_id}: {e}")
        connection_manager.disconnect(websocket) # Ensure cleanup


# --- REST API Endpoint ---
@app.post("/start_research", status_code=status.HTTP_202_ACCEPTED)
async def start_research(payload: InitialTopic):
    """
    Initiates the research process by creating placeholder tasks.
    """
    logger.info(f"Received research request for topic: {payload.topic}")
    try:
        # --- Placeholder Task Creation ---
        # In the future, the Planning Agent would do this dynamically
        plan_task = await task_manager.add_task(f"Plan research for: {payload.topic}")
        search_task = await task_manager.add_task(f"Initial search for: {payload.topic} keywords") # Placeholder
        filter_task = await task_manager.add_task(f"Filter results for: {payload.topic}")
        analyze_task = await task_manager.add_task(f"Analyze & Synthesize findings for: {payload.topic}")
        report_task = await task_manager.add_task(f"Generate report for: {payload.topic}")

        # --- Trigger the Orchestrator (Next Step) ---
        # In Sub-Task B/C, we would start the actual execution loop here.
        # For now, we just create the tasks.
        logger.info("Placeholder tasks created. Orchestrator would start execution now.")

        return {"message": "Research task initiated", "tasks_created": [plan_task.id, search_task.id, filter_task.id, analyze_task.id, report_task.id]}

    except Exception as e:
        logger.exception(f"Error starting research for topic {payload.topic}: {e}") # Log full traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate research process: {str(e)}"
        )

# --- Add Orchestrator Endpoint/Logic Later ---
# This is where the main loop driving agent execution will reside.


# --- Run the app (for local development) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server...")
    # Use reload=True for development convenience
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)