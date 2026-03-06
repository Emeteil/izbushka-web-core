from flask import request
from settings import *
from settings import current_emotion
from authorization import _verify_token
from flask_socketio import disconnect

connected_clients = set()

@socketio.on("connect")
def handle_connect():
    token = request.args.get('token') or request.headers.get('Authorization')

    if token and token.startswith('Bearer '):
        token = token[7:]

    if not token:
        disconnect()
        return

    payload = _verify_token(token)
    if not payload:
        disconnect()
        return

    connected_clients.add(request.sid)

    socketio.emit("emotion_changed", {
        "emotion": current_emotion,
        "source": "system"
    }, room=request.sid)

    connected = (com_link_connection and
                com_link_connection.ser and
                com_link_connection.ser.is_open)
    socketio.emit("connection_status", {
        "connected": connected,
        "port": settings.get("com_link_rt_port")
    }, room=request.sid)

@socketio.on("set_emotion")
def handle_set_emotion(data):
    global current_emotion
    
    token = request.args.get('token') or request.headers.get('Authorization')
    
    if token and token.startswith('Bearer '):
        token = token[7:]
    
    if not token:
        socketio.emit("error", {
            "message": "Authentication required"
        }, room=request.sid)
        return
    
    payload = _verify_token(token)
    if not payload:
        socketio.emit("error", {
            "message": "Invalid token"
        }, room=request.sid)
        return
    
    emotion = data.get("emotion")
    valid_emotions = settings["emotions"]["ids"]
    
    if emotion not in valid_emotions:
        socketio.emit("error", {
            "message": f"Invalid emotion. Must be one of: {', '.join(valid_emotions)}"
        }, room=request.sid)
        return
    
    current_emotion = emotion
    
    socketio.emit("emotion_changed", {
        "emotion": emotion,
        "source": "websocket",
        "client_id": request.sid
    })
    
    print(f"Emotion changed to {emotion} by client {request.sid}")

@socketio.on("get_emotion")
def handle_get_emotion():
    socketio.emit("current_emotion", {
        "emotion": current_emotion
    }, room=request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    connected_clients.discard(request.sid)

@socketio.on("get_sensor_data")
def handle_get_sensor_data():
    if request.sid not in connected_clients:
        socketio.emit("error", {"message": "Not authenticated"}, room=request.sid)
        return

    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
        socketio.emit("error", {"message": "ComLink RT connection not established"}, room=request.sid)
        return

    if com_link_commands:
        data = {}

        cmd = com_link_commands.get('distance')
        if cmd and cmd.is_subscribed and cmd.last_distance is not None:
            data['distance'] = {"distance_cm": cmd.last_distance}

        cmd = com_link_commands.get('gyro')
        if cmd and cmd.is_subscribed and cmd.last_data is not None:
            data['gyro'] = {
                "accel": cmd.get_acceleration(cmd.last_data),
                "gyro": cmd.get_rotation(cmd.last_data),
                "temperature": cmd.get_temperature(cmd.last_data)
            }

        cmd = com_link_commands.get('millis')
        if cmd and cmd.is_subscribed and cmd.last_data is not None:
            data['millis'] = {"millis": cmd.last_data}

        socketio.emit("current_sensor_data", data, room=request.sid)

@socketio.on("send_command")
def handle_send_command(data):
    if request.sid not in connected_clients:
        socketio.emit("error", {"message": "Not authenticated"}, room=request.sid)
        return

    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
        socketio.emit("error", {"message": "ComLink RT connection not established"}, room=request.sid)
        return

    if not isinstance(data, dict):
        socketio.emit("error", {"message": "Invalid command data"}, room=request.sid)
        return

    command_type = data.get("type")
    command_data = data.get("data", {})
    wait_response = data.get("wait_response", True)

    try:
        if command_type == "ping":
            cmd = com_link_commands.get('ping')
            if cmd:
                result = cmd.execute()
                socketio.emit("command_result", {
                    "type": "ping",
                    "success": result is not None
                }, room=request.sid)

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
                    socketio.emit("command_result", {
                        "type": "motors",
                        "command": subcommand,
                        "success": success
                    }, room=request.sid)

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
                    socketio.emit("command_result", {
                        "type": "servo",
                        "command": subcommand,
                        "success": success
                    }, room=request.sid)

        else:
            socketio.emit("error", {"message": f"Unknown command type: {command_type}"}, room=request.sid)

    except ValueError as e:
        socketio.emit("error", {"message": str(e)}, room=request.sid)
    except Exception as e:
        socketio.emit("error", {"message": f"Command execution failed: {str(e)}"}, room=request.sid)