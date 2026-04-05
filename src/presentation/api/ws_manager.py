import asyncio
import logging
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        logging.info(f"WebSocket подключен: user {user_id} (всего: {len(self._connections[user_id])})")

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logging.info(f"WebSocket отключен: user {user_id}")

    async def send_to_user(self, user_id: int, data: dict):
        if user_id not in self._connections:
            return
        dead = []
        for ws in self._connections[user_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[user_id].discard(ws)
        if user_id in self._connections and not self._connections[user_id]:
            del self._connections[user_id]

    def has_connections(self, user_id: int) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0


ws_manager = ConnectionManager()
