import logging
import json
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Dict, Optional, List, Annotated
from models import InitialTopic, UserCommand, Task, TaskType, JobStatus, StatusUpdate, TaskSuccessMessage, JobFailedMessage
from websocket_manager import ConnectionManager
from task_manager import TaskManager
from orchestrator import Orchestrator
from contextlib import asynccontextmanager
from pathlib import Path
import uuid
from starlette.websockets import WebSocketState

# Import DB settings and handler
from config.settings import DBSettings
from database_layer.database import Database
from database_layer.base_db_handler import BaseDBHandler

from api.auth_router import router as auth_router

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()



# --- Global instances (to be initialized in lifespan context) ---
db_instance: Optional[Database] = None
task_manager_instance: Optional[TaskManager] = None
websocket_manager_instance: Optional[ConnectionManager] = None
orchestrator_instance: Optional[Orchestrator] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    global db_instance, task_manager_instance, websocket_manager_instance, orchestrator_instance
    logger.info("Application startup: Initializing resources...")

    try:
        # Initialize Database (ensure DB_PATH is set in settings)
        db_settings=DBSettings()
        db_instance = await Database.get_instance(db_path=db_settings.connection_string)
        logger.info("Database instance created and initialized.")

        # Initialize TaskManager with the database instance
        task_manager_instance = TaskManager(database=db_instance)
        logger.info("TaskManager initialized.")

        # Initialize WebSocketManager
        websocket_manager_instance = ConnectionManager()
        logger.info("WebSocketManager initialized.")

        # Initialize Orchestrator
        # Prompt library path can be configured or use default
        prompt_lib_path = str(Path(__file__).parent / "llm_providers" / "prompts.json")
        orchestrator_instance = Orchestrator(
            task_manager=task_manager_instance,
            websocket_manager=websocket_manager_instance,
            database=db_instance,
            prompt_library_path=prompt_lib_path
        )
        logger.info("Orchestrator initialized.")
        logger.info("Application startup complete.")
        yield
    except Exception as e:
        logger.critical(f"Application startup failed: {e}", exc_info=True)
        # Optionally re-raise or handle to prevent app from starting in a bad state
        raise
    finally:
        logger.info("Application shutdown: Cleaning up resources...")
        if orchestrator_instance:
            await orchestrator_instance.shutdown()
            logger.info("Orchestrator shutdown complete.")
        if db_instance:
            await db_instance.close()
            logger.info("Database connection closed.")
        # Websocket manager might have cleanup if needed (e.g., closing all connections)
        if websocket_manager_instance:
             # await websocket_manager_instance.close_all_connections() # If such method exists
             logger.info("WebSocketManager resources released (if any).")
        logger.info("Application shutdown complete.")

app = FastAPI(title="Research Agent API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # TODO: change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to provide DB handler to routes
async def get_db_handler() -> BaseDBHandler:
    return db_instance

# Override the get_db_handler dependency in auth_router
auth_router.dependencies = [Depends(get_db_handler)]

# Include routers
app.include_router(auth_router)


# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>Research Agent API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                p { color: #666; }
                code { background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>Research Agent API</h1>
            <p>The API is up and running. Visit <code>/docs</code> for the API documentation.</p>
        </body>
    </html>
    """
#commenting out below coz i refined them in lifespan
#connection_manager = ConnectionManager()
#task_manager = TaskManager(connection_manager=connection_manager)
#orchestrator = Orchestrator(task_manager=task_manager)
#task_manager.set_orchestrator(orchestrator) # Link back

# --- HTML for WebSocket Testing (Update JS) ---
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Research Agent</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #ffffff;
                color: #333;
                height: 100vh;
                display: flex;
            }
            
            /* Sidebar */
            .sidebar {
                width: 200px;
                background-color: #f8f9fa;
                border-right: 1px solid #e9ecef;
                padding: 20px 0;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            
            .sidebar-logo {
                padding: 0 20px 20px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .sidebar-logo img {
                height: 24px;
            }
            
            .menu-item {
                padding: 10px 20px;
                display: flex;
                align-items: center;
                gap: 12px;
                color: #4d4d4d;
                text-decoration: none;
                font-size: 14px;
            }
            
            .menu-item i {
                width: 20px;
                text-align: center;
            }
            
            .menu-item:hover {
                background-color: #f1f3f5;
            }
            
            .active {
                font-weight: 600;
            }
            
            /* Main content */
            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding-top: 60px;
                overflow-y: auto;
            }
            
            /* Search bar */
            .search-container {
                width: 100%;
                max-width: 700px;
                text-align: center;
                margin-bottom: 40px;
            }
            
            .search-header {
                font-size: 32px;
                font-weight: 600;
                color: #333;
                margin-bottom: 20px;
            }
            
            .search-bar {
                width: 100%;
                position: relative;
                margin-bottom: 20px;
            }
            
            .search-input {
                width: 100%;
                padding: 14px 20px;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
                font-size: 16px;
                transition: all 0.3s;
                outline: none;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }
            
            .search-input:focus {
                border-color: #2563eb;
                box-shadow: 0 2px 15px rgba(37, 99, 235, 0.1);
            }
            
            .search-button {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 15px;
                font-weight: 500;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .search-button:hover {
                background-color: #1d4ed8;
            }
            
            .search-button:disabled {
                background-color: #9ca3af;
                cursor: not-allowed;
            }
            
            /* Plan list */
            .plan-container {
                width: 100%;
                max-width: 700px;
                margin-top: 20px;
                display: none; /* Hidden initially, shown after search */
            }
            
            .plan-header {
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 15px;
                color: #333;
            }
            
            #plan-display {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            #plan-display li {
                margin-bottom: 10px;
                padding: 12px 16px;
                border-radius: 8px;
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                display: flex;
                align-items: center;
                gap: 12px;
                transition: all 0.2s;
            }
            
            #plan-display li .icon {
                font-size: 16px;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
            }
            
            #plan-display li.pending .icon {
                background-color: #e5e7eb;
                color: #4b5563;
            }
            
            #plan-display li.running .icon {
                background-color: #dbeafe;
                color: #2563eb;
                animation: pulse 1.5s infinite;
            }
            
            #plan-display li.completed .icon {
                background-color: #dcfce7;
                color: #16a34a;
            }
            
            #plan-display li.failed .icon {
                background-color: #fee2e2;
                color: #dc2626;
            }
            
            @keyframes pulse {
                0% { opacity: 0.7; }
                50% { opacity: 1; }
                100% { opacity: 0.7; }
            }
            
            /* Report output */
            #report-output-container {
                width: 100%;
                max-width: 700px;
                margin-top: 40px;
                display: none; /* Hidden initially */
            }
            
            .report-header {
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 20px;
                color: #333;
            }
            
            #report-output {
                padding: 20px;
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                font-size: 15px;
                line-height: 1.6;
                overflow-y: auto;
                max-height: 600px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }
            
            #report-output h1 {
                font-size: 24px;
                margin-top: 1.5em;
                margin-bottom: 0.75em;
                font-weight: 600;
            }
            
            #report-output h2 {
                font-size: 20px;
                margin-top: 1.25em;
                margin-bottom: 0.5em;
                font-weight: 600;
            }
            
            #report-output h3 {
                font-size: 18px;
                margin-top: 1em;
                margin-bottom: 0.5em;
                font-weight: 600;
            }
            
            #report-output p {
                margin-bottom: 1em;
                font-size: 15px;
            }
            
            #report-output code {
                background-color: #f1f5f9;
                padding: 2px 4px;
                border-radius: 4px;
                font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 0.9em;
            }
            
            #report-output pre {
                background-color: #f1f5f9;
                padding: 12px;
                border-radius: 6px;
                overflow-x: auto;
                margin-bottom: 1em;
            }
            
            #report-output blockquote {
                border-left: 3px solid #e5e7eb;
                padding-left: 16px;
                margin-left: 0;
                color: #4b5563;
            }
            
            /* Error area (hidden initially) */
            #error-area {
                width: 100%;
                max-width: 700px;
                margin-top: 20px;
                padding: 12px 16px;
                border-radius: 8px;
                background-color: #fee2e2;
                border-left: 3px solid #ef4444;
                color: #b91c1c;
                font-weight: 500;
                display: none;
            }
            
            /* Hidden elements */
            .hidden {
                display: none !important;
            }
        </style>
    </head>
    <body>
        <!-- Hidden inputs for internal use -->
        <input type="hidden" id="jobIdInput">
        <input type="hidden" id="taskIdInput">
        
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-logo">
                <i class="fas fa-robot" style="color: #2563eb;"></i>
                <span style="font-weight: 600; font-size: 18px;">Research AI</span>
            </div>
            
            <a href="#" class="menu-item active">
                <i class="fas fa-home"></i>
                <span>Home</span>
            </a>
            
            <a href="#" class="menu-item">
                <i class="fas fa-compass"></i>
                <span>Discover</span>
            </a>
            
            <a href="#" class="menu-item">
                <i class="fas fa-layer-group"></i>
                <span>Spaces</span>
            </a>
            
            <a href="#" class="menu-item">
                <i class="fas fa-book"></i>
                <span>Library</span>
            </a>
        </div>
        
        <!-- Main content -->
        <div class="main-content">
            <!-- Search container -->
            <div class="search-container">
                <h1 class="search-header">What do you want to know?</h1>
                
                <div class="search-bar">
                    <textarea 
                        id="topicInput" 
                        class="search-input" 
                        placeholder="Ask anything..."
                        rows="1" 
                        style="resize: none; overflow: hidden;">What is the impact of AI on software development jobs?</textarea>
                </div>
                
                <button id="start-button" class="search-button" onclick="startResearch(event)">
                    <i class="fas fa-search"></i> Search
                </button>
            </div>
            
            <!-- Error area (initially hidden) -->
            <div id="error-area"></div>
            
            <!-- Plan container (initially hidden) -->
            <div class="plan-container" id="plan-container">
                <h2 class="plan-header">Research plan:</h2>
                <ul id="plan-display"></ul>
            </div>
            
            <!-- Report output (initially hidden) -->
            <div id="report-output-container">
                <h2 class="report-header">Research report:</h2>
                <div id="report-output"></div>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket(`ws://${location.host}/ws/frontend_client_${Date.now()}`); // Unique client ID
            const planDisplayUl = document.getElementById('plan-display');
            const planContainer = document.getElementById('plan-container');
            const reportOutputDiv = document.getElementById('report-output');
            const reportContainer = document.getElementById('report-output-container');
            const errorAreaDiv = document.getElementById('error-area');
            const startButton = document.getElementById('start-button');
            const topicInput = document.getElementById('topicInput');
            const jobIdInput = document.getElementById('jobIdInput');
            const taskIdInput = document.getElementById('taskIdInput');

            let currentJobId = null; // Track the current job

            // Auto-resize textarea as user types
            topicInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
            });
            
            // Set initial height
            window.addEventListener('load', function() {
                topicInput.style.height = 'auto';
                topicInput.style.height = (topicInput.scrollHeight) + 'px';
            });

            ws.onopen = function(event) { 
                console.log("WebSocket connected");
            };
            
            ws.onerror = function(event) {
                errorAreaDiv.textContent = "Connection error. Please refresh the page and try again.";
                errorAreaDiv.style.display = 'block';
                console.error("WebSocket Error: ", event);
            };
            
            ws.onclose = function(event) {
                if (!event.wasClean) {
                    errorAreaDiv.textContent = `Connection closed unexpectedly. Please refresh the page.`;
                    errorAreaDiv.style.display = 'block';
                }
                console.log("WebSocket Closed:", event);
                startButton.disabled = false;
                startButton.innerHTML = '<i class="fas fa-search"></i> Search';
            };

            ws.onmessage = function(event) {
                let data;
                try {
                    data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    console.warn("Received non-JSON message:", event.data);
                    errorAreaDiv.textContent = "Received invalid response from server.";
                    errorAreaDiv.style.display = 'block';
                }
            };

            function handleMessage(data) {
                console.log("Received message:", data);

                // Update current Job ID input if relevant
                if (data.job_id && !jobIdInput.value) {
                    jobIdInput.value = data.job_id;
                    currentJobId = data.job_id;
                }

                switch (data.type) {
                    case 'final_report':
                        if (data.job_id !== currentJobId) return;
                        try {
                            reportOutputDiv.innerHTML = marked.parse(data.report_markdown);
                            reportContainer.style.display = 'block';
                        } catch(e) {
                            console.error("Error parsing Markdown:", e);
                            reportOutputDiv.innerHTML = `<pre>${escapeHtml(data.report_markdown)}</pre>`;
                            reportContainer.style.display = 'block';
                        }
                        startButton.disabled = false;
                        startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                        
                        // Mark all plan items as complete
                        document.querySelectorAll('#plan-display li:not(.completed)').forEach(li => {
                            li.classList.remove('pending', 'running');
                            li.classList.add('completed');
                            const iconSpan = li.querySelector('.icon');
                            if(iconSpan) iconSpan.innerHTML = '<i class="fas fa-check"></i>';
                        });
                        break;

                    case 'task_success':
                        if (data.job_id !== currentJobId) return;
                        const taskItem = document.getElementById('task-item-' + data.task_id);
                        if (taskItem) {
                            taskItem.classList.remove('pending', 'running');
                            taskItem.classList.add('completed');
                            const iconSpan = taskItem.querySelector('.icon');
                            if(iconSpan) iconSpan.innerHTML = '<i class="fas fa-check"></i>';
                            console.log(`Marked task ${data.task_id} as complete.`);
                            
                            // Find next task and mark it as running
                            const nextTask = taskItem.nextElementSibling;
                            if (nextTask && nextTask.classList.contains('pending')) {
                                nextTask.classList.remove('pending');
                                nextTask.classList.add('running');
                                const nextIconSpan = nextTask.querySelector('.icon');
                                if(nextIconSpan) nextIconSpan.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                            }
                        }
                        break;

                    case 'job_status':
                        if (data.job_id !== currentJobId) return;
                        // Re-enable button ONLY if job definitively completes or fails
                        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                            startButton.disabled = false;
                            startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                        }
                        break;

                    case 'job_failed':
                        if (data.job_id !== currentJobId) return;
                        errorAreaDiv.textContent = `Research failed: ${data.error_message}`;
                        errorAreaDiv.style.display = 'block';
                        startButton.disabled = false;
                        startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                        
                        // Mark incomplete tasks as failed
                        document.querySelectorAll('#plan-display li:not(.completed)').forEach(li => {
                            li.classList.remove('pending', 'running');
                            li.classList.add('failed');
                            const iconSpan = li.querySelector('.icon');
                            if(iconSpan) iconSpan.innerHTML = '<i class="fas fa-times"></i>';
                        });
                        break;

                    case 'job_error':
                        errorAreaDiv.textContent = `Error: ${data.detail || 'Unknown error during research.'}`;
                        errorAreaDiv.style.display = 'block';
                        startButton.disabled = false;
                        startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                        break;

                    default:
                        console.log("Received unhandled message type:", data.type, data);
                        if (data.error) {
                            errorAreaDiv.textContent = `Error: ${data.error}`;
                            errorAreaDiv.style.display = 'block';
                        }
                }
            }

            // --- Helper Functions ---
            function escapeHtml(unsafe) {
                if (!unsafe) return "";
                return unsafe
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
            }

            // --- Updated startResearch ---
            async function startResearch(event) {
                event.preventDefault();
                const topic = topicInput.value;
                if (!topic) { 
                    alert("Please enter a research topic or question.");
                    return; 
                }

                // UI Reset
                startButton.disabled = true;
                startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Researching...';
                reportOutputDiv.innerHTML = "";
                reportContainer.style.display = 'none';
                planDisplayUl.innerHTML = "";
                planContainer.style.display = 'none';
                errorAreaDiv.textContent = "";
                errorAreaDiv.style.display = "none";
                currentJobId = null;
                jobIdInput.value = "";
                taskIdInput.value = "";

                try {
                    const response = await fetch('/start_job', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', },
                        body: JSON.stringify({ query: topic })
                    });

                    const result = await response.json();

                    if (response.ok && result.job_id && result.plan) {
                        console.log("Research job started:", result);
                        currentJobId = result.job_id;
                        jobIdInput.value = currentJobId;
                        
                        // Display plan
                        planContainer.style.display = 'block';
                        planDisplayUl.innerHTML = "";
                        
                        result.plan.forEach((task, index) => {
                            const li = document.createElement('li');
                            li.id = `task-item-${task.id}`;
                            
                            // First task is running, others are pending
                            if (index === 0) {
                                li.classList.add('running');
                            } else {
                                li.classList.add('pending');
                            }

                            const iconSpan = document.createElement('span');
                            iconSpan.classList.add('icon');
                            if (index === 0) {
                                iconSpan.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; // Running icon
                            } else {
                                iconSpan.innerHTML = '<i class="fas fa-clock"></i>'; // Pending icon
                            }
                            li.appendChild(iconSpan);

                            const descSpan = document.createElement('span');
                            descSpan.textContent = task.description;
                            li.appendChild(descSpan);

                            // Hidden task ID for internal use
                            const idSpan = document.createElement('span');
                            idSpan.style.display = 'none';
                            idSpan.textContent = task.id;
                            li.appendChild(idSpan);

                            planDisplayUl.appendChild(li);
                        });

                    } else {
                        const errorDetail = result.detail || response.statusText || 'Unknown error starting research.';
                        console.error("Error starting research:", errorDetail);
                        errorAreaDiv.textContent = `Error starting research: ${errorDetail}`;
                        errorAreaDiv.style.display = 'block';
                        startButton.disabled = false;
                        startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                    }
                } catch (error) {
                    console.error("Network error:", error);
                    errorAreaDiv.textContent = "Network error. Please check your connection and try again.";
                    errorAreaDiv.style.display = 'block';
                    startButton.disabled = false;
                    startButton.innerHTML = '<i class="fas fa-search"></i> Search';
                }
            }
        </script>
    </body>
</html>
"""

@app.post("/start_job", status_code=status.HTTP_202_ACCEPTED)
async def start_new_job(payload: Dict[str, str], request: Request):
    """
    Initiates a new research job, returning the job ID and the initial plan.
    """
    user_query = payload.get("query")
    if not user_query:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'query' field in request body.")

    # Extract client_id from request headers (front end is doing already , have to check if this is good way of implementing to communicate to frontend or else change the entire communication strategy)
    client_id = request.headers.get("x-client-id", "default-client")
    logger.info(f"Received job request for query: '{user_query}' from client_id: {client_id}")
    
    try:
        # Call orchestrator's start_job with the client_id
        job_id, planned_tasks_data = await orchestrator_instance.start_job(user_query=user_query, client_id=client_id)
        logger.info(f"Job {job_id} successfully started for client {client_id} with {len(planned_tasks_data)} planned tasks")

        # Return both job_id and the plan
        return {
            "message": "Research job initiated successfully.",
            "job_id": job_id,
            "plan": planned_tasks_data # Return the list of task dicts directly
        }

    except (ValueError, RuntimeError) as e: # Catch planning or validation errors
         logger.error(f"Failed to plan or start job for query '{user_query}': {e}", exc_info=True)
         # Send error back to client immediately
         await websocket_manager_instance.broadcast_json({
             "type": "job_error",
             "detail": f"Failed to initiate job: {e}"
         })
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail=f"Failed to initiate job: {e}"
         )
    except Exception as e:
        logger.exception(f"Unexpected error starting job for query {user_query}: {e}")
        await websocket_manager_instance.broadcast_json({
             "type": "job_error",
             "detail": f"Internal server error during job initiation."
         })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}"
        )

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    if not websocket_manager_instance:
        logger.error("WebsocketManager not initialized. Cannot accept WebSocket connection.")
        # Unfortunately, we can't send an HTTP error code here easily after WS handshake starts.
        # We can close the connection with a code.
        await websocket.close(code=1011) # Internal error
        return

    await websocket_manager_instance.connect(websocket, client_id)
    logger.info(f"Client {client_id} connected via WebSocket.")
    try:
        while True:
            data = await websocket.receive_text()
            # For now, backend primarily sends updates. If frontend needs to send commands:
            # logger.info(f"Received message from {client_id}: {data}")
            # Here you would parse `data` (e.g., JSON) and handle commands if any.
            # Example: if orchestrator_instance and task_manager_instance:
            #     parsed_data = json.loads(data)
            #     if parsed_data.get("type") == "user_command":
            #         await task_manager_instance.handle_user_command(parsed_data.get("payload"))
            # For this refactor, we assume one-way (server to client) for progress primarily.
            await websocket.send_text(f"Message received by server for {client_id}. Echo: {data}") # Basic echo for testing

    except WebSocketDisconnect:
        websocket_manager_instance.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected from WebSocket.")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for client {client_id}: {e}", exc_info=True)
        # Try to close gracefully if not already disconnected
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1011) # Internal server error
        websocket_manager_instance.disconnect(client_id) # Ensure cleanup using client_id

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.get("/status/{job_id}")
async def get_job_status_api(job_id: str):
    """API endpoint to get the status of a specific job."""
    if not orchestrator_instance:
        raise HTTPException(status_code=503, detail="Service not ready.")
    job_details = await orchestrator_instance.get_job_status(job_id)
    if not job_details:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job_details # job_details is already a dict from DB layer

@app.get("/jobs")
async def get_all_jobs_api(limit: int = 20, offset: int = 0):
    """API endpoint to get a list of all jobs."""
    if not orchestrator_instance:
        raise HTTPException(status_code=503, detail="Service not ready.")
    jobs = await orchestrator_instance.get_all_jobs(limit=limit, offset=offset)
    return jobs # jobs is already a list of dicts

@app.post("/jobs/{job_id}/cancel", status_code=200)
async def cancel_job_api(job_id: str):
    if not orchestrator_instance:
        raise HTTPException(status_code=503, detail="Service not ready.")
    try:
        await orchestrator_instance.cancel_job(job_id)
        return {"job_id": job_id, "message": "Job cancellation requested."}
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

# --- Run the app ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for Multi-Agent Research Backend (Clean UI)...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
