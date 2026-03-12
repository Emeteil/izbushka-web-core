from typing import Dict, List, Any, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.rooms: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self._remove_user_from_all_rooms(user_id)

    async def send_personal_message(self, message: Any, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json(message)

    async def broadcast(self, message: Any):
        for user_id in self.active_connections:
            await self.send_personal_message(message, user_id)

    async def join_room(self, user_id: str, room_id: str):
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(user_id)

    async def leave_room(self, user_id: str, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def send_to_room(self, message: Any, room_id: str):
        if room_id in self.rooms:
            for user_id in self.rooms[room_id]:
                await self.send_personal_message(message, user_id)

    def _remove_user_from_all_rooms(self, user_id: str):
        rooms_to_delete = []
        for room_id, members in self.rooms.items():
            members.discard(user_id)
            if not members:
                rooms_to_delete.append(room_id)
        for room_id in rooms_to_delete:
            del self.rooms[room_id]

manager = ConnectionManager()