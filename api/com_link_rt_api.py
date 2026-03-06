from authorization import login_required
from settings import *
from utils.api_response import *
from flask import request

def _check_connection():
    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
        raise ApiError(503, "ComLink RT connection is not established")

@app.route("/api/sensors/distance", methods=["GET"])
@login_required()
def get_distance(payload):
    _check_connection()
    cmd = com_link_commands.get('distance')
    if not cmd:
        raise ApiError(500, "Distance command not initialized")

    if cmd.is_subscribed:
        data = cmd.last_distance
        if data is None:
            raise ApiError(503, "Distance data not available")
        return apiResponse({"distance_cm": data})
    else:
        data = cmd.execute()
        if data is None:
            raise ApiError(503, "Failed to get distance data")
        return apiResponse({"distance_cm": data})

@app.route("/api/sensors/gyro", methods=["GET"])
@login_required()
def get_gyro(payload):
    _check_connection()
    cmd = com_link_commands.get('gyro')
    if not cmd:
        raise ApiError(500, "Gyro command not initialized")

    if cmd.is_subscribed:
        data = cmd.last_data
        if data is None:
            raise ApiError(503, "Gyro data not available")
        return apiResponse({
            "accel": cmd.get_acceleration(data),
            "gyro": cmd.get_rotation(data),
            "temperature": cmd.get_temperature(data)
        })
    else:
        data = cmd.execute()
        if data is None:
            raise ApiError(503, "Failed to get gyro data")
        return apiResponse({
            "accel": cmd.get_acceleration(data),
            "gyro": cmd.get_rotation(data),
            "temperature": cmd.get_temperature(data)
        })

@app.route("/api/sensors/millis", methods=["GET"])
@login_required()
def get_millis(payload):
    _check_connection()
    cmd = com_link_commands.get('millis')
    if not cmd:
        raise ApiError(500, "Millis command not initialized")

    if cmd.is_subscribed:
        data = cmd.last_data
        if data is None:
            raise ApiError(503, "Millis data not available")
        return apiResponse({"millis": data})
    else:
        data = cmd.execute()
        if data is None:
            raise ApiError(503, "Failed to get millis data")
        return apiResponse({"millis": data})

@app.route("/api/commands/ping", methods=["POST"])
@login_required()
def ping_robot(payload):
    _check_connection()
    cmd = com_link_commands.get('ping')
    if not cmd:
        raise ApiError(500, "Ping command not initialized")

    result = cmd.execute()
    return apiResponse({"ping_success": result is not None})

@app.route("/api/commands/motors", methods=["POST"])
@login_required()
def control_motors(payload):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    data = request.get_json()
    if not data:
        raise ApiError(400, "Request body required")

    command = data.get("command")
    if not command:
        raise ApiError(400, "Command parameter required")

    try:
        if command == "set_speed":
            motor_mask = data.get("motor_mask", cmd.MOTOR_BOTH)
            speed_left = data.get("speed_left", 0)
            speed_right = data.get("speed_right", 0)
            result = cmd.set_speed(motor_mask, speed_left, speed_right)
        elif command == "set_direction":
            motor_mask = data.get("motor_mask", cmd.MOTOR_BOTH)
            direction_left = data.get("direction_left", cmd.DIRECTION_STOP)
            direction_right = data.get("direction_right", cmd.DIRECTION_STOP)
            result = cmd.set_direction(motor_mask, direction_left, direction_right)
        elif command == "move_forward":
            speed = data.get("speed", 150)
            result = cmd.move_forward(speed)
        elif command == "move_backward":
            speed = data.get("speed", 150)
            result = cmd.move_backward(speed)
        elif command == "turn_left":
            speed = data.get("speed", 150)
            result = cmd.turn_left(speed)
        elif command == "turn_right":
            speed = data.get("speed", 150)
            result = cmd.turn_right(speed)
        elif command == "stop":
            result = cmd.stop_all()
        elif command == "brake":
            result = cmd.brake()
        else:
            raise ApiError(400, f"Unknown command: {command}")

        return apiResponse({"command": command, "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@app.route("/api/commands/servo", methods=["POST"])
@login_required()
def control_servo(payload):
    _check_connection()
    cmd = com_link_commands.get('servo')
    if not cmd:
        raise ApiError(500, "Servo command not initialized")

    data = request.get_json()
    if not data:
        raise ApiError(400, "Request body required")

    command = data.get("command")
    if not command:
        raise ApiError(400, "Command parameter required")

    try:
        if command == "move_immediate":
            channel = data.get("channel", 0)
            angle = data.get("angle", 90)
            result = cmd.move_immediate(channel, angle)
        elif command == "move_smooth":
            channel = data.get("channel", 0)
            angle = data.get("angle", 90)
            step_delay = data.get("step_delay", 50)
            result = cmd.move_smooth_high(channel, angle, step_delay)
        else:
            raise ApiError(400, f"Unknown command: {command}")

        return apiResponse({"command": command, "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@app.route("/api/connection/status", methods=["GET"])
@login_required()
def get_connection_status(payload):
    connected = (com_link_connection and
                com_link_connection.ser and
                com_link_connection.ser.is_open)

    subscriptions = {}
    if connected and com_link_commands:
        for name, cmd in com_link_commands.items():
            if hasattr(cmd, 'is_subscribed'):
                subscriptions[name] = cmd.is_subscribed

    return apiResponse({
        "connected": connected,
        "port": settings.get("com_link_rt_port"),
        "subscriptions": subscriptions
    })