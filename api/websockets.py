from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.connection_manager import manager
from authorization import get_current_user_ws
from settings import app, settings, com_link_connection, com_link_commands
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
        
        connected = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)
        await websocket.send_json({
            "event": "system.connection_status",
            "data": {
                "connected": connected,
                "port": settings.get("com_link_rt_port")
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
                    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
                        await websocket.send_json({"event": "system.error", "data": {"message": "ComLink RT connection not established"}})
                        continue
                        
                    if com_link_commands:
                        cmd = com_link_commands.get('distance')
                        if getattr(cmd, 'is_subscribed', False) and getattr(cmd, 'last_distance', None) is not None:
                            sensor_resp['distance'] = {"distance_cm": cmd.last_distance}
                            
                        cmd = com_link_commands.get('gyro')
                        if getattr(cmd, 'is_subscribed', False) and getattr(cmd, 'last_data', None) is not None:
                            sensor_resp['gyro'] = {
                                "accel": cmd.get_acceleration(cmd.last_data),
                                "gyro": cmd.get_rotation(cmd.last_data),
                                "temperature": cmd.get_temperature(cmd.last_data)
                            }
                            
                        cmd = com_link_commands.get('millis')
                        if getattr(cmd, 'is_subscribed', False) and getattr(cmd, 'last_data', None) is not None:
                            sensor_resp['millis'] = {"millis": cmd.last_data}

                    await websocket.send_json({"event": "sensor.data", "data": sensor_resp})
                
                elif event.startswith("robot."):
                    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
                        await websocket.send_json({"event": "system.error", "data": {"message": "ComLink RT connection not established"}})
                        continue
                    
                    target = event.split(".")[1]
                    action = payload_data.get("action")
                    wait_response = payload_data.get("wait_response", True)
                    
                    try:
                        if target == "ping":
                            cmd = com_link_commands.get('ping')
                            if cmd:
                                result = cmd.execute()
                                await websocket.send_json({"event": "command.result", "data": {
                                    "target": "ping",
                                    "success": result is not None
                                }})
                        elif target == "motors":
                            cmd = com_link_commands.get('motors')
                            if cmd:
                                success = False
                                if action == "set_speed":
                                    motor_mask = payload_data.get("motor_mask", cmd.MOTOR_BOTH)
                                    speed_left = payload_data.get("speed_left", 0)
                                    speed_right = payload_data.get("speed_right", 0)
                                    success = cmd.set_speed(motor_mask, speed_left, speed_right, wait_response=wait_response)
                                elif action == "move_forward":
                                    speed = payload_data.get("speed", 150)
                                    success = cmd.move_forward(speed, wait_response=wait_response)
                                elif action == "move_backward":
                                    speed = payload_data.get("speed", 150)
                                    success = cmd.move_backward(speed, wait_response=wait_response)
                                elif action == "turn_left":
                                    speed = payload_data.get("speed", 150)
                                    success = cmd.turn_left(speed, wait_response=wait_response)
                                elif action == "turn_right":
                                    speed = payload_data.get("speed", 150)
                                    success = cmd.turn_right(speed, wait_response=wait_response)
                                elif action == "stop":
                                    success = cmd.stop_all(wait_response=wait_response)
                                elif action == "brake":
                                    success = cmd.brake(wait_response=wait_response)

                                if wait_response:
                                    await websocket.send_json({"event": "command.result", "data": {
                                        "target": "motors",
                                        "action": action,
                                        "success": success
                                    }})
                        elif target == "servo":
                            cmd = com_link_commands.get('servo')
                            if cmd:
                                success = False
                                if action == "move_immediate":
                                    channel = payload_data.get("channel", 0)
                                    angle = payload_data.get("angle", 90)
                                    success = cmd.move_immediate(channel, angle, wait_response=wait_response)
                                elif action == "move_smooth":
                                    channel = payload_data.get("channel", 0)
                                    angle = payload_data.get("angle", 90)
                                    step_delay = payload_data.get("step_delay", 50)
                                    success = cmd.move_smooth_high(channel, angle, step_delay, wait_response=wait_response)

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
