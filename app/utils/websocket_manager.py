import json
import asyncio
import logging
from typing import Dict, Optional
from fastapi import WebSocket
import redis.asyncio as redis
from core.security import decode_token
from core.config import get_settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, redis_url: Optional[str] = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = redis.from_url(self.redis_url)
        self.active_connections: Dict[int, WebSocket] = {}
        self.subscribe_tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, token: str) -> Optional[int]:
        await websocket.accept()
        user_id = None
        try:
            payload = decode_token(token)
            user_id = payload.get("user_id")
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user_id in token")
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            await websocket.close(code=1008, reason="Invalid token")
            return None

        await self.redis_client.setex(f"user_ws:{user_id}", 3600 * 24, "connected")
        self.active_connections[user_id] = websocket

        subscribe_task = asyncio.create_task(
            self._subscribe_to_user(user_id, websocket)
        )
        self.subscribe_tasks[user_id] = subscribe_task

        logger.info(f"User {user_id} connected via WebSocket")
        return user_id

    async def _subscribe_to_user(self, user_id: int, websocket: WebSocket):
        """Background task: Subscribe to user's Redis channel and forward messages to WS."""
        pubsub = self.redis_client.pubsub()
        channel = f"ws:{user_id}"
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel {channel} for user {user_id}")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_text(json.dumps(data))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Subscribe error for user {user_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            logger.info(f"Unsubscribed from {channel}")

    async def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            ws = self.active_connections.pop(user_id)
            try:
                await ws.close(code=1000)
            except Exception:
                pass

        if user_id in self.subscribe_tasks:
            self.subscribe_tasks[user_id].cancel()
            del self.subscribe_tasks[user_id]

        await self.redis_client.delete(f"user_ws:{user_id}")
        logger.info(f"User {user_id} disconnected")

    async def send_personal(self, message: dict, user_id: int):
        """Send message to specific user: in-memory if active, else publish to channel."""
        try:
            if user_id in self.active_connections:
                await self.active_connections[user_id].send_text(json.dumps(message))
                return True
            channel = f"ws:{user_id}"
            await self.redis_client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Send error to user {user_id}: {e}")
            return False

    async def broadcast_to_chat(
        self, message: dict, chat_id: int, exclude_user_id: Optional[int] = None
    ):
        """Broadcast to both users in chat via personal sends."""
        pass

    async def heartbeat(self, user_id: int):
        """Optional: Send periodic heartbeat to keep connection alive."""
        await self.send_personal({"type": "heartbeat"}, user_id)

    async def is_online(self, user_id: int) -> bool:
        """Check if user is online via Redis flag."""
        status = await self.redis_client.get(f"user_ws:{user_id}")
        return status == b"connected"
