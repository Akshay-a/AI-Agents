Required variables to run this program:
LIVEKIT_URL=<your LiveKit server URL>
LIVEKIT_API_KEY=<your API Key>
LIVEKIT_API_SECRET=<your API Secret>
DEEPGRAM_API_KEY=<To use other providers, press Enter for now and edit .env.local>
CARTESIA_API_KEY=<To use other providers, press Enter for now and edit .env.local>
DEEPSEEK_API_KEY=<To use other providers, press Enter for now and edit .env.local>
GROQ_API_KEY=<To use other providers, press Enter for now and edit .env.local>
ZAPIER_MCP_SERVER=<To use other providers, press Enter for now and edit .env.local>

Below is mermaid diagram for Customer and AI agent interaction:

sequenceDiagram
    participant Caller
    participant Twilio
    participant LiveKit as LiveKit Server
    participant Dispatch as Dispatch Engine
    participant Triage as Triage Agent
    participant Scheduler as Scheduling Agent
    participant Inquiry as Inquiry Agent
    participant Human as Human Handoff
    participant External as External APIs
    participant Metrics as Observability

    %% Initial Call Setup
    Caller->>Twilio: Incoming Call
    Twilio->>LiveKit: SIP INVITE
    LiveKit->>Dispatch: Create Room & Apply Rules
    Dispatch->>Triage: Dispatch to Triage Agent
    
    %% Triage Process
    Triage->>Caller: "Hello! How can I help you today?"
    Caller->>Triage: "I need to schedule an appointment"
    Triage->>Metrics: Log interaction metrics
    
    %% Routing Decision
    Triage->>Scheduler: Route to Scheduling Agent
    Scheduler->>Caller: "I'll help you schedule. What type of appointment?"
    
    %% Scheduling Flow
    Caller->>Scheduler: "Doctor appointment for next week"
    Scheduler->>External: Check availability (Cal.com/Google)
    External->>Scheduler: Available slots
    Scheduler->>Caller: "I have slots available on..."
    Caller->>Scheduler: "Tuesday at 2 PM works"
    Scheduler->>External: Book appointment
    External->>Scheduler: Confirmation
    Scheduler->>Caller: "Appointment booked! You'll receive confirmation."
    
    %% Alternative Flow - Inquiry
    Note over Caller,Inquiry: Alternative: Inquiry/Complaint Flow
    Triage->>Inquiry: Route to Inquiry Agent
    Inquiry->>External: Query knowledge base (MCP)
    External->>Inquiry: Search results
    
    %% Escalation Flow
    Note over Inquiry,Human: If out of scope
    Inquiry->>Human: Transfer to Human Agent
    Human->>External: Connect to human queue
    Human->>Caller: "Connecting you to a specialist..."
    
    %% Metrics Collection
    par Continuous Monitoring
        Triage->>Metrics: Performance metrics
        Scheduler->>Metrics: Success/failure rates
        Inquiry->>Metrics: Resolution metrics
        Human->>Metrics: Escalation metrics
    end
    
    Metrics->>Metrics: Generate quality score
    Metrics->>Metrics: Send alerts if needed
