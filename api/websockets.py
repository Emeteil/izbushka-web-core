from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.connection_manager import manager
from utils.tracing import trace_scope
from authorization import get_current_user_ws
from settings import app, settings, com_link_connection, transport_bus, sensor_service, emotion_registry
from services.emotion_registry import EmotionNotFoundError
import json

router = APIRouter(tags=["Websockets"])

def _connection_state() -> dict:
    is_hardware = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)
    vl = transport_bus.get("virtual_link")
    is_virtual = vl is not None and vl.enabled and getattr(vl, "is_connected", False)
    return {
        "connected": is_hardware or is_virtual,
        "port": settings.get("com_link_rt_port"),
        "transport": transport_bus.status(),
    }

async def _send_error(ws: WebSocket, message: str) -> None:
    await ws.send_json({"event": "system.error", "data": {"message": message}})

async def _handle_emotion(ws: WebSocket, action: str, payload: dict, user_id: str) -> None:
    if action == "get":
        await ws.send_json({"event": "emotion.current", "data": {"emotion": emotion_registry.current}})
        return
    try:
        emotion_registry.set_current(payload.get("emotion"))
    except EmotionNotFoundError:
        await _send_error(ws, "Invalid emotion")
        return
    await manager.broadcast({
        "event": "system.emotion_changed",
        "data": {"emotion": emotion_registry.current, "source": "websocket", "client_id": user_id},
    })

async def _handle_sensor_request(ws: WebSocket) -> None:
    if not transport_bus.has_active():
        await ws.send_json({"event": "sensor.data", "data": {}})
        return
    await ws.send_json({"event": "sensor.data", "data": sensor_service.get_all()})

MOTORS_ACTIONS = {
    "set_speed":     ("set_speed",     ("motor_mask", "speed_left", "speed_right")),
    "move_forward":  ("move_forward",  ("speed",)),
    "move_backward": ("move_backward", ("speed",)),
    "turn_left":     ("turn_left",     ("speed",)),
    "turn_right":    ("turn_right",    ("speed",)),
    "stop":          ("stop_all",      ()),
    "brake":         ("brake",         ()),
}

MOTOR_DEFAULTS = {"motor_mask": 0x03, "speed_left": 0, "speed_right": 0, "speed": 150}

SERVO_ACTIONS = {
    "move_immediate":   ("move_immediate",   {"channel": 0, "angle": 90}),
    "move_smooth":      ("move_smooth_high", {"channel": 0, "angle": 90, "step_delay_ms": 50}),
}

def _kwargs_for(payload: dict, keys, defaults: dict) -> dict:
    return {k: payload.get(k, defaults.get(k)) for k in keys}

async def _execute_motors(ws: WebSocket, action: str, payload: dict, wait_response: bool) -> None:
    mapping = MOTORS_ACTIONS.get(action)
    if mapping is None:
        await _send_error(ws, f"Unknown motors action: {action}")
        return
    bus_action, keys = mapping
    kwargs = _kwargs_for(payload, keys, MOTOR_DEFAULTS)
    kwargs["wait_response"] = wait_response
    success = transport_bus.execute("motors", bus_action, **kwargs)
    if wait_response:
        await ws.send_json({"event": "command.result", "data": {"target": "motors", "action": action, "success": success}})

async def _execute_servo(ws: WebSocket, action: str, payload: dict, wait_response: bool) -> None:
    mapping = SERVO_ACTIONS.get(action)
    if mapping is None:
        await _send_error(ws, f"Unknown servo action: {action}")
        return
    bus_action, defaults = mapping
    kwargs = {k: payload.get(k, v) for k, v in defaults.items()}
    if action == "move_smooth":
        kwargs["step_delay_ms"] = payload.get("step_delay", defaults["step_delay_ms"])
    kwargs["wait_response"] = wait_response
    success = transport_bus.execute("servo", bus_action, **kwargs)
    if wait_response:
        await ws.send_json({"event": "command.result", "data": {"target": "servo", "action": action, "success": success}})

async def _execute_ping(ws: WebSocket) -> None:
    result = transport_bus.execute("ping", "execute")
    await ws.send_json({"event": "command.result", "data": {"target": "ping", "success": result is not None}})

async def _handle_robot(ws: WebSocket, target: str, payload: dict) -> None:
    if not transport_bus.has_active():
        await _send_error(ws, "No active transport subscribers")
        return
    action = payload.get("action")
    wait_response = payload.get("wait_response", True)
    try:
        if target == "ping":
            await _execute_ping(ws)
        elif target == "motors":
            await _execute_motors(ws, action, payload, wait_response)
        elif target == "servo":
            await _execute_servo(ws, action, payload, wait_response)
        else:
            await _send_error(ws, f"Unknown robot target: {target}")
    except Exception as e:
        await _send_error(ws, str(e))

async def _dispatch(ws: WebSocket, event: str, payload: dict, user_id: str) -> None:
    if event == "emotion.set":
        await _handle_emotion(ws, "set", payload, user_id)
    elif event == "emotion.get":
        await _handle_emotion(ws, "get", payload, user_id)
    elif event == "sensor.get_data":
        await _handle_sensor_request(ws)
    elif event and event.startswith("robot."):
        await _handle_robot(ws, event.split(".", 1)[1], payload)
    else:
        await _send_error(ws, f"Unknown event namespace: {event}")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    payload = await get_current_user_ws(websocket)
    if not payload:
        return

    user_id = payload.get("user_id", "anonymous")
    await manager.connect(websocket, user_id)

    try:
        await websocket.send_json({
            "event": "system.emotion_changed",
            "data": {"emotion": emotion_registry.current, "source": "system"},
        })
        await websocket.send_json({"event": "system.connection_status", "data": _connection_state()})

        while True:
            try:
                data = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            with trace_scope():
                await _dispatch(websocket, data.get("event"), data.get("data", {}), user_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

app.include_router(router)