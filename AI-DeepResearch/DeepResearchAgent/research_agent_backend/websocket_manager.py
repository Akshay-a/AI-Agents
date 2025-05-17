import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client {client_id} ({websocket.client}) connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        websocket = self.active_connections.pop(client_id, None)
        if websocket:
            logger.info(f"WebSocket client {client_id} ({websocket.client}) disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, client_id: str):
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                # Safely create a preview of the message for logging
                message_preview = str(message)[:400] + "..." if len(str(message)) > 100 else str(message)
                logger.info(f"Sending personal message to client {client_id}: {message_preview}")
                await websocket.send_text(message)
                logger.info(f"Successfully sent personal message to client {client_id}")
            except Exception as e:
                logger.error(f"Failed to send personal message to client {client_id} ({websocket.client}): {e}")
        else:
            logger.warning(f"Cannot send personal message: client {client_id} not found in active connections")

    async def send_personal_json(self, data: dict, client_id: str):
        json_str = json.dumps(data)
        # Safely create a preview of the JSON for logging
        json_preview = json_str[:100] + "..." if len(json_str) > 100 else json_str
        logger.info(f"Sending JSON data with type '{data.get('type', 'unknown')}' to client {client_id}: {json_preview}")
        await self.send_personal_message(json_str, client_id)

    async def broadcast(self, message: str):
        disconnected_client_ids = []
        active_connections_snapshot = dict(self.active_connections)
        
        # Safely create a preview of the message for logging
        message_preview = str(message)[:100] + "..." if len(str(message)) > 100 else str(message)
        logger.info(f"Broadcasting message to {len(active_connections_snapshot)} clients: {message_preview}")
        
        for client_id, connection in active_connections_snapshot.items():
            try:
                await connection.send_text(message)
                logger.info(f"Successfully broadcast to client {client_id}")
            except Exception as e:
                logger.error(f"Failed to broadcast to client {client_id} ({connection.client}): {e}. Marking for removal.")
                disconnected_client_ids.append(client_id)

        for cid_to_remove in disconnected_client_ids:
            self.disconnect(cid_to_remove)

    async def broadcast_json(self, data: dict):
        json_str = json.dumps(data)
        # Safely create a preview of the JSON for logging
        json_preview = json_str[:100] + "..." if len(json_str) > 100 else json_str
        logger.info(f"Broadcasting JSON data with type '{data.get('type', 'unknown')}': {json_preview}")
        await self.broadcast(json_str)