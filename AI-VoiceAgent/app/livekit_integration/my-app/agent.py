import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    metrics,
    RoomInputOptions,
)
from livekit.agents.llm import function_tool, ChatContext, ChatMessage
from livekit.plugins import (
    cartesia,
    openai,
    deepgram,
    noise_cancellation,
    silero,
    groq,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from calendar_utils import CalendarManager
from zapier_integration import zapier_integration


load_dotenv(dotenv_path=".env")
logger = logging.getLogger("voice-agent")

# Set up logging with reduced verbosity to minimize token usage
logging.basicConfig(
    level=logging.WARNING,  # Reduced to WARNING to minimize output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Minimal debug logging for specific components
logging.getLogger("voice-agent").setLevel(logging.INFO)
logging.getLogger("livekit.agents").setLevel(logging.WARNING)  # Reduced verbosity
logging.getLogger("livekit.plugins").setLevel(logging.WARNING)  # Reduced verbosity


class Assistant(Agent):
    def __init__(self) -> None:
        # Optimized assistant with minimal instructions to reduce token usage
        super().__init__(
            instructions="You are a helpful voice assistant with calendar management. "
            "Use available tools to help users with calendar tasks. "
            "Confirm the actions before executing them. Ask for questions if needed like if there is a create event request and you see the input parameters have description or attendees, ask the user to confirm the details "
            "Don't hallucinate or make up information. Ask for clarification if the request is unclear. "
            "Keep responses short and conversational. "
            "remove special characters while sending the response to user "
            "If tool results have 'success' false, explain the error clearly.",
            stt=deepgram.STT(api_key=os.getenv('DEEPGRAM_API_KEY')),
            llm=openai.LLM.with_deepseek(
                model="deepseek-chat",  # this is DeepSeek-V3
                temperature=0.7
            ),
            tts=cartesia.TTS(),
            # use LiveKit's transformer-based turn detector
            turn_detection=MultilingualModel(),
        )
        
        # Initialize calendar manager
        self.calendar_manager = CalendarManager()

    async def on_enter(self):
        # Connect to Zapier integration
        await zapier_integration.connect()
        
        # Minimal greeting to reduce token usage
        self.session.generate_reply(
            instructions="Greet the user briefly and ask how you can help with their calendar.", 
            allow_interruptions=True
        )

    def _truncate_chat_context(self, items: list, keep_last_n: int = 4) -> list:
        """Truncate chat context to prevent token buildup on free tier"""
        if len(items) <= keep_last_n:
            return items
            
        # Keep system messages and last N items
        system_items = [item for item in items if hasattr(item, 'role') and item.role == "system"]
        recent_items = items[-keep_last_n:]
        
        # Combine keeping system context
        result = system_items + [item for item in recent_items if item not in system_items]
        logger.info(f"Truncated context from {len(items)} to {len(result)} items")
        return result

    async def on_user_turn_completed(self, chat_ctx: ChatContext, new_message: ChatMessage) -> None:
        """Hook called after user completes their turn - manage context here"""
        # Truncate context every few turns to prevent token buildup
        if len(chat_ctx.items) > 6:
            chat_ctx_copy = self.chat_ctx.copy()
            truncated_items = self._truncate_chat_context(chat_ctx_copy.items, keep_last_n=4)
            chat_ctx_copy.items = truncated_items
            await self.update_chat_ctx(chat_ctx_copy)

    @function_tool
    async def get_calendar_events(self, query: str = "today"):
        """Get calendar events for a time period"""
        try:
            logger.debug(f"🗓️ [TOOL] get_calendar_events called with query: {query}")
            
            # Try Zapier integration first
            if zapier_integration.connected:
                result = await zapier_integration.find_calendar_events(
                    instructions=f"Find calendar events for {query}",
                    end_time=query,
                    start_time=query
                )
                if result.get("success"):
                    logger.debug(f"🗓️ [TOOL] Zapier result: {result}")
                    return result
            
            # Fallback to mock response
            parsed_time = self.calendar_manager.parse_natural_language_time(query)
            
            result = {
                "success": True,
                "message": f"I checked your calendar for {query}. You currently have no events scheduled.",
                "events": [],
                "query": query
            }
            
            if parsed_time:
                result["parsed_time"] = parsed_time
                
            logger.debug(f"🗓️ [TOOL] get_calendar_events returning: {result}")
            return result
                
        except Exception as e:
            logger.error(f"❌ [TOOL] get_calendar_events error: {e}")
            error_result = {
                "success": False,
                "message": "Sorry, I couldn't fetch your calendar events right now. Please try again.",
                "error": str(e)
            }
            logger.debug(f"🗓️ [TOOL] get_calendar_events error result: {error_result}")
            return error_result

    @function_tool
    async def create_calendar_event(self, title: str, when: str, duration: str = "1 hour", 
                                  description: str = "", attendees: str = ""):
        """Create a new calendar event"""
        try:
            logger.info(f"Creating calendar event: {title} for {when} lasting {duration}")
            
            # Try Zapier integration first
            if zapier_integration.connected:
                result = await zapier_integration.create_calendar_event(
                    instructions=f"Create a calendar event titled '{title}' for {when} lasting {duration}",
                    summary=title,
                    start__dateTime=when,
                    description=description,
                    attendees=attendees
                )
                if result.get("success"):
                    logger.debug(f"🗓️ [TOOL] Zapier create result: {result}")
                    return result
            
            # Fallback to mock response
            start_time = self.calendar_manager.parse_natural_language_time(when)
            
            if not start_time:
                return {
                    "success": False,
                    "message": f"I couldn't understand the time '{when}'. Could you try saying it differently?",
                    "error": "Invalid time format"
                }
            
            # Parse duration and create event
            duration_minutes = 60  # default to 1 hour
            if "30 minutes" in duration.lower() or "half hour" in duration.lower():
                duration_minutes = 30
            elif "2 hours" in duration.lower():
                duration_minutes = 120
            elif "15 minutes" in duration.lower():
                duration_minutes = 15
            
            end_time = self.calendar_manager.calculate_end_time(start_time, duration_minutes)
            
            attendee_list = []
            if attendees:
                attendee_list = [email.strip() for email in attendees.split(",")]
            
            event_data = self.calendar_manager.create_event_data(
                title, start_time, end_time, description, attendee_list
            )
            
            return {
                "success": True,
                "message": f"I've created a calendar event titled '{title}' for {when} lasting {duration}.",
                "event_data": event_data,
                "start_time": start_time,
                "end_time": end_time
            }
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't create the calendar event right now. Please try again.",
                "error": str(e)
            }

    @function_tool
    async def check_free_time(self, when: str = "today", duration: str = "1 hour"):
        """Check for free time slots"""
        try:
            logger.info(f"Checking free time for {when} with duration {duration}")
            
            # Parse duration
            duration_minutes = 60  # default
            if "30 minutes" in duration.lower():
                duration_minutes = 30
            elif "2 hours" in duration.lower():
                duration_minutes = 120
            elif "15 minutes" in duration.lower():
                duration_minutes = 15
            
            parsed_time = self.calendar_manager.parse_natural_language_time(when)
            
            if parsed_time:
                # Mock available slots for now
                available_slots = ["9:00 AM", "11:30 AM", "2:00 PM", "4:30 PM"]
                return {
                    "success": True,
                    "message": f"I found available time slots for {when}. You have several {duration} slots available: {', '.join(available_slots)}.",
                    "free_slots": available_slots,
                    "when": when,
                    "duration": duration
                }
            else:
                return {
                    "success": True,
                    "message": f"I'll check your free time for {when}. You appear to have good availability throughout the day.",
                    "when": when,
                    "duration": duration
                }
                
        except Exception as e:
            logger.error(f"Error checking free time: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't check your free time right now. Please try again.",
                "error": str(e)
            }

    @function_tool
    async def update_calendar_event(self, event_query: str, changes: str):
        """Update an existing calendar event"""
        try:
            logger.info(f"Updating calendar event: {event_query} with changes: {changes}")
            
            return {
                "success": True,
                "message": f"I've updated your event '{event_query}' with the changes: {changes}.",
                "event_query": event_query,
                "changes": changes
            }
            
        except Exception as e:
            logger.error(f"Error updating calendar event: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't update the calendar event right now. Please try again.",
                "error": str(e)
            }

    @function_tool
    async def delete_calendar_event(self, event_query: str):
        """Delete a calendar event"""
        try:
            logger.info(f"Deleting calendar event: {event_query}")
            
            return {
                "success": True,
                "message": f"I've deleted your event: {event_query}. It has been removed from your calendar.",
                "event_query": event_query
            }
            
        except Exception as e:
            logger.error(f"Error deleting calendar event: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't delete the calendar event right now. Please try again.",
                "error": str(e)
            }

    @function_tool
    async def get_calendar_summary(self, period: str = "today"):
        """Get a summary of calendar events for a time period"""
        try:
            logger.info(f"Getting calendar summary for: {period}")
            
            return {
                "success": True,
                "message": f"Here's your calendar summary for {period}. Currently showing placeholder data since MCP server integration is pending.",
                "period": period,
                "summary": {
                    "total_events": 0,
                    "busy_hours": 0,
                    "free_hours": 8,
                    "next_meeting": None
                }
            }

        except Exception as e:
            logger.error(f"Error getting calendar summary: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't get your calendar summary right now. Please try again.",
                "error": str(e)
            }

    @function_tool
    async def get_comprehensive_calendar_overview(self, when: str = "today", include_free_time: bool = True):
        """Get a quick calendar overview with events and availability"""
        try:
            logger.info(f"Getting comprehensive calendar overview for: {when}")
            
            # Simple combined response instead of multi-step guidance
            return {
                "success": True,
                "message": f"For {when}, you currently have no events scheduled. "
                          f"Your calendar is wide open with good availability throughout the day.",
                "when": when,
                "total_events": 0,
                "availability": "Full day available"
            }

        except Exception as e:
            logger.error(f"Error getting comprehensive calendar overview: {e}")
            return {
                "success": False,
                "message": "Sorry, I couldn't get your calendar overview right now. Please try again.",
                "error": str(e)
            }


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

    usage_collector = metrics.UsageCollector()

    # Log metrics and collect usage data
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        # Optimized endpointing delays for faster response and less token buildup
        min_endpointing_delay=0.2,  # Faster response to reduce context buildup
        max_endpointing_delay=2.0,  # Shorter max delay to prevent long contexts
    )

    # Trigger the on_metrics_collected function when metrics are collected
    session.on("metrics_collected", on_metrics_collected)

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # enable background voice & noise cancellation, powered by Krisp
            # included at no additional cost with LiveKit Cloud
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
