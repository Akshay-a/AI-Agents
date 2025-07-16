"""
Main entry point for the Voice AI Backend MVP.
"""

import logging
import asyncio
from app.core import config
from app.agent.agno_processing_logic import AgnoAgent
from app.livekit_integration.livekit_agent_worker import LiveKitAgentWorker
from app.livekit_integration.voice_pipeline_orchestrator import VoicePipelineOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """
    Main application entry point.
    """
    logger.info("Starting Voice AI Backend MVP")
    
    try:
        # Initialize the agent
        agent = AgnoAgent(api_key=config.GROQ_API_KEY)
        logger.info("Agent initialized")
        
        # Initialize the voice pipeline orchestrator
        orchestrator = VoicePipelineOrchestrator(agent=agent)
        logger.info("Voice pipeline orchestrator initialized")
        
        # Initialize the LiveKit agent worker
        worker = LiveKitAgentWorker(
            api_key=config.LIVEKIT_API_KEY,
            api_secret=config.LIVEKIT_API_SECRET,
            ws_url=config.LIVEKIT_WS_URL
        )
        logger.info("LiveKit agent worker initialized")
        
        # Start the worker
        await worker.start()
        
        # Keep the application running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        if 'worker' in locals():
            await worker.stop()
        logger.info("Voice AI Backend MVP shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 