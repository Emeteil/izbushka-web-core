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
            "event": "emotion_changed",
            "data": {
                "emotion": g_settings.current_emotion,
                "source": "system"
            }
        })
        
        connected = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)
        await websocket.send_json({
            "event": "connection_status",
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
                
                if event == "set_emotion":
                    emotion = payload_data.get("emotion")
                    valid_emotions = settings["emotions"]["ids"]
                    if emotion in valid_emotions:
                        g_settings.current_emotion = emotion
                        await manager.broadcast({
                            "event": "emotion_changed",
                            "data": {
                                "emotion": emotion,
                                "source": "websocket",
                                "client_id": user_id
                            }
                        })
                    else:
                        await websocket.send_json({"event": "error", "data": {"message": "Invalid emotion"}})
                
                elif event == "get_emotion":
                    await websocket.send_json({"event": "current_emotion", "data": {"emotion": g_settings.current_emotion}})
                
                elif event == "get_sensor_data":
                    sensor_resp = {}
                    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
                        await websocket.send_json({"event": "error", "data": {"message": "ComLink RT connection not established"}})
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

                    await websocket.send_json({"event": "current_sensor_data", "data": sensor_resp})
                
                elif event == "send_command":
                    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
                        await websocket.send_json({"event": "error", "data": {"message": "ComLink RT connection not established"}})
                        continue
                    
                    command_type = payload_data.get("type")
                    command_data = payload_data.get("data", {})
                    wait_response = payload_data.get("wait_response", True)
                    
                    try:
                        if command_type == "ping":
                            cmd = com_link_commands.get('ping')
                            if cmd:
                                result = cmd.execute()
                                await websocket.send_json({"event": "command_result", "data": {
                                    "type": "ping",
                                    "success": result is not None
                                }})
                        elif command_type == "motors":
                            cmd = com_link_commands.get('motors')
                            if cmd:
                                subcommand = command_data.get("command")
                                success = False
                                if subcommand == "set_speed":
                                    motor_mask = command_data.get("motor_mask", cmd.MOTOR_BOTH)
                                    speed_left = command_data.get("speed_left", 0)
                                    speed_right = command_data.get("speed_right", 0)
                                    success = cmd.set_speed(motor_mask, speed_left, speed_right, wait_response=wait_response)
                                elif subcommand == "move_forward":
                                    speed = command_data.get("speed", 150)
                                    success = cmd.move_forward(speed, wait_response=wait_response)
                                elif subcommand == "move_backward":
                                    speed = command_data.get("speed", 150)
                                    success = cmd.move_backward(speed, wait_response=wait_response)
                                elif subcommand == "turn_left":
                                    speed = command_data.get("speed", 150)
                                    success = cmd.turn_left(speed, wait_response=wait_response)
                                elif subcommand == "turn_right":
                                    speed = command_data.get("speed", 150)
                                    success = cmd.turn_right(speed, wait_response=wait_response)
                                elif subcommand == "stop":
                                    success = cmd.stop_all(wait_response=wait_response)
                                elif subcommand == "brake":
                                    success = cmd.brake(wait_response=wait_response)

                                if wait_response:
                                    await websocket.send_json({"event": "command_result", "data": {
                                        "type": "motors",
                                        "command": subcommand,
                                        "success": success
                                    }})
                        elif command_type == "servo":
                            cmd = com_link_commands.get('servo')
                            if cmd:
                                subcommand = command_data.get("command")
                                success = False
                                if subcommand == "move_immediate":
                                    channel = command_data.get("channel", 0)
                                    angle = command_data.get("angle", 90)
                                    success = cmd.move_immediate(channel, angle, wait_response=wait_response)
                                elif subcommand == "move_smooth":
                                    channel = command_data.get("channel", 0)
                                    angle = command_data.get("angle", 90)
                                    step_delay = command_data.get("step_delay", 50)
                                    success = cmd.move_smooth_high(channel, angle, step_delay, wait_response=wait_response)

                                if wait_response:
                                    await websocket.send_json({"event": "command_result", "data": {
                                        "type": "servo",
                                        "command": subcommand,
                                        "success": success
                                    }})
                        else:
                            await websocket.send_json({"event": "error", "data": {"message": f"Unknown command type: {command_type}"}})
                    except Exception as e:
                        await websocket.send_json({"event": "error", "data": {"message": str(e)}})
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

app.include_router(router)
