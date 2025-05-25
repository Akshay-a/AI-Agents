import asyncio
import json
import logging
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")
try:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
except ImportError:
    print("fastmcp not installed. Install with: pip install fastmcp")
    Client = None
    StreamableHttpTransport = None

logger = logging.getLogger(__name__)

class ZapierCalendarIntegration:
    def __init__(self):
        self.client = None
        self.connected = False
        
    async def connect(self):
        """Connect to Zapier MCP server"""
        if not Client or not StreamableHttpTransport:
            logger.error("fastmcp not available")
            return False
            
        try:
            server_url = os.getenv("ZAPIER_MCP_SERVER_URL")
            transport = StreamableHttpTransport(server_url)
            self.client = Client(transport=transport)
            
            await self.client.__aenter__()
            logger.info("Connected to Zapier MCP server")
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zapier MCP server: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Zapier MCP server"""
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
                logger.info("Disconnected from Zapier MCP server")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self.client = None
                self.connected = False
    
    async def find_calendar_events(self, instructions: str, **kwargs) -> Dict[str, Any]:
        """Find calendar events using Zapier Google Calendar integration"""
        if not self.connected or not self.client:
            return {
                "success": False,
                "message": "Not connected to calendar service",
                "error": "MCP connection not available"
            }
        
        try:
            result = await self.client.call_tool(
                "google_calendar_find_event",
                {
                    "instructions": instructions,
                    **kwargs
                }
            )
            
            if result and len(result) > 0:
                if hasattr(result[0], 'text'):
                    try:
                        json_result = json.loads(result[0].text)
                        return {
                            "success": True,
                            "result": json_result,
                            "message": "Successfully retrieved calendar events"
                        }
                    except json.JSONDecodeError:
                        return {
                            "success": True,
                            "result": result[0].text,
                            "message": "Retrieved calendar events"
                        }
                else:
                    return {
                        "success": True,
                        "result": str(result[0]),
                        "message": "Retrieved calendar events"
                    }
            else:
                return {
                    "success": False,
                    "message": "No events found",
                    "result": None
                }
                
        except Exception as e:
            logger.error(f"Error finding calendar events: {e}")
            return {
                "success": False,
                "message": f"Error finding calendar events: {str(e)}",
                "error": str(e)
            }
    
    async def create_calendar_event(self, instructions: str, **kwargs) -> Dict[str, Any]:
        """Create calendar event using Zapier Google Calendar integration"""
        if not self.connected or not self.client:
            return {
                "success": False,
                "message": "Not connected to calendar service",
                "error": "MCP connection not available"
            }
        
        try:
            result = await self.client.call_tool(
                "google_calendar_create_detailed_event",
                {
                    "instructions": instructions,
                    **kwargs
                }
            )
            
            if result and len(result) > 0:
                if hasattr(result[0], 'text'):
                    try:
                        json_result = json.loads(result[0].text)
                        return {
                            "success": True,
                            "result": json_result,
                            "message": "Successfully created calendar event"
                        }
                    except json.JSONDecodeError:
                        return {
                            "success": True,
                            "result": result[0].text,
                            "message": "Created calendar event"
                        }
                else:
                    return {
                        "success": True,
                        "result": str(result[0]),
                        "message": "Created calendar event"
                    }
            else:
                return {
                    "success": False,
                    "message": "Failed to create event",
                    "result": None
                }
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return {
                "success": False,
                "message": f"Error creating calendar event: {str(e)}",
                "error": str(e)
            }

# Global instance
zapier_integration = ZapierCalendarIntegration() 