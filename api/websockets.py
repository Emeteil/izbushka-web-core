from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.connection_manager import manager
from authorization import get_current_user_ws
from settings import app, settings, com_link_connection, com_link_commands, transport_bus
import settings as g_settings
import json

router = APIRouter(tags=["Websockets"])

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
            "data": {
                "emotion": g_settings.current_emotion,
                "source": "system"
            }
        })
        
        is_hardware = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)
        vl = transport_bus.get("virtual_link")
        is_virtual = vl is not None and vl.enabled and getattr(vl, 'is_connected', False)
        connected = is_hardware or is_virtual
        await websocket.send_json({
            "event": "system.connection_status",
            "data": {
                "connected": connected,
                "port": settings.get("com_link_rt_port"),
                "transport": transport_bus.status()
            }
        })

        while True:
            text_data = await websocket.receive_text()
            try:
                data = json.loads(text_data)
                event = data.get("event")
                payload_data = data.get("data", {})
                
                if event == "emotion.set":
                    emotion = payload_data.get("emotion")
                    valid_emotions = settings["emotions"]["ids"]
                    if emotion in valid_emotions:
                        g_settings.current_emotion = emotion
                        await manager.broadcast({
                            "event": "system.emotion_changed",
                            "data": {
                                "emotion": emotion,
                                "source": "websocket",
                                "client_id": user_id
                            }
                        })
                    else:
                        await websocket.send_json({"event": "system.error", "data": {"message": "Invalid emotion"}})
                
                elif event == "emotion.get":
                    await websocket.send_json({"event": "emotion.current", "data": {"emotion": g_settings.current_emotion}})
                
                elif event == "sensor.get_data":
                    sensor_resp = {}
                    
                    cmd_dist = com_link_commands.get('distance') if com_link_commands else None
                    if cmd_dist and getattr(cmd_dist, 'is_subscribed', False) and getattr(cmd_dist, 'last_distance', None) is not None:
                        sensor_resp['distance'] = {"distance_cm": cmd_dist.last_distance}
                    elif transport_bus.has_active():
                        dist = transport_bus.execute("distance", "execute")
                        if dist is not None: sensor_resp['distance'] = {"distance_cm": dist}
                        
                    cmd_gyro = com_link_commands.get('gyro') if com_link_commands else None
                    if cmd_gyro and getattr(cmd_gyro, 'is_subscribed', False) and getattr(cmd_gyro, 'last_data', None) is not None:
                        sensor_resp['gyro'] = {
                            "accel": cmd_gyro.get_acceleration(cmd_gyro.last_data),
                            "gyro": cmd_gyro.get_rotation(cmd_gyro.last_data),
                            "temperature": cmd_gyro.get_temperature(cmd_gyro.last_data)
                        }
                    elif transport_bus.has_active():
                        gyro = transport_bus.execute("gyro", "execute")
                        if gyro is not None: sensor_resp['gyro'] = gyro
                        
                    cmd_millis = com_link_commands.get('millis') if com_link_commands else None
                    if cmd_millis and getattr(cmd_millis, 'is_subscribed', False) and getattr(cmd_millis, 'last_data', None) is not None:
                        sensor_resp['millis'] = {"millis": cmd_millis.last_data}
                    elif transport_bus.has_active():
                        millis = transport_bus.execute("millis", "execute")
                        if millis is not None: sensor_resp['millis'] = {"millis": millis}

                    await websocket.send_json({"event": "sensor.data", "data": sensor_resp})
                
                elif event.startswith("robot."):
                    if not transport_bus.has_active():
                        await websocket.send_json({"event": "system.error", "data": {"message": "No active transport subscribers"}})
                        continue
                    
                    target = event.split(".")[1]
                    action = payload_data.get("action")
                    wait_response = payload_data.get("wait_response", True)
                    
                    try:
                        if target == "ping":
                            result = transport_bus.execute("ping", "execute")
                            await websocket.send_json({"event": "command.result", "data": {
                                "target": "ping",
                                "success": result is not None
                            }})
                        elif target == "motors":
                            success = False
                            if action == "set_speed":
                                motor_mask = payload_data.get("motor_mask", 0x03)
                                speed_left = payload_data.get("speed_left", 0)
                                speed_right = payload_data.get("speed_right", 0)
                                success = transport_bus.execute("motors", "set_speed",
                                    motor_mask=motor_mask, speed_left=speed_left,
                                    speed_right=speed_right, wait_response=wait_response)
                            elif action == "move_forward":
                                speed = payload_data.get("speed", 150)
                                success = transport_bus.execute("motors", "move_forward",
                                    speed=speed, wait_response=wait_response)
                            elif action == "move_backward":
                                speed = payload_data.get("speed", 150)
                                success = transport_bus.execute("motors", "move_backward",
                                    speed=speed, wait_response=wait_response)
                            elif action == "turn_left":
                                speed = payload_data.get("speed", 150)
                                success = transport_bus.execute("motors", "turn_left",
                                    speed=speed, wait_response=wait_response)
                            elif action == "turn_right":
                                speed = payload_data.get("speed", 150)
                                success = transport_bus.execute("motors", "turn_right",
                                    speed=speed, wait_response=wait_response)
                            elif action == "stop":
                                success = transport_bus.execute("motors", "stop_all",
                                    wait_response=wait_response)
                            elif action == "brake":
                                success = transport_bus.execute("motors", "brake",
                                    wait_response=wait_response)

                            if wait_response:
                                await websocket.send_json({"event": "command.result", "data": {
                                    "target": "motors",
                                    "action": action,
                                    "success": success
                                }})
                        elif target == "servo":
                            success = False
                            if action == "move_immediate":
                                channel = payload_data.get("channel", 0)
                                angle = payload_data.get("angle", 90)
                                success = transport_bus.execute("servo", "move_immediate",
                                    channel=channel, angle=angle, wait_response=wait_response)
                            elif action == "move_smooth":
                                channel = payload_data.get("channel", 0)
                                angle = payload_data.get("angle", 90)
                                step_delay = payload_data.get("step_delay", 50)
                                success = transport_bus.execute("servo", "move_smooth_high",
                                    channel=channel, angle=angle, step_delay_ms=step_delay,
                                    wait_response=wait_response)

                            if wait_response:
                                await websocket.send_json({"event": "command.result", "data": {
                                    "target": "servo",
                                    "action": action,
                                    "success": success
                                }})
                        else:
                            await websocket.send_json({"event": "system.error", "data": {"message": f"Unknown robot target: {target}"}})
                    except Exception as e:
                        await websocket.send_json({"event": "system.error", "data": {"message": str(e)}})
                else:
                    await websocket.send_json({"event": "system.error", "data": {"message": f"Unknown event namespace: {event}"}})
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

app.include_router(router)
