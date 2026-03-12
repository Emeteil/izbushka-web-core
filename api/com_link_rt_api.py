from fastapi import APIRouter, Depends, Request
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from settings import app, com_link_connection, com_link_commands, settings
from api.schemas.com_link import (
    DistanceResponse, GyroResponse, MillisResponse, CommandSuccessResponse,
    MotorsCommandRequest, ServoCommandRequest, ConnectionStatusResponse
)

router = APIRouter(prefix="/api", tags=["ComLink"])

def _check_connection():
    if not com_link_connection or not com_link_connection.ser or not com_link_connection.ser.is_open:
        raise ApiError(503, "ComLink RT connection is not established")

@router.get("/sensors/distance", 
    response_model=DistanceResponse, 
    summary="Получить дистанцию (в см)", 
    description="Запрашивает или возвращает последние данные с датчика дистанции (в сантиметрах). Поддерживает кэширование, если датчик настроен на подписку."
)
async def get_distance(payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('distance')
    if not cmd:
        raise ApiError(500, "Distance command not initialized")

    if getattr(cmd, 'is_subscribed', False):
        data = cmd.last_distance
        if data is None:
            raise ApiError(503, "Distance data not available")
        return apiResponse({"distance_cm": data})
    else:
        data = cmd.execute()
        if data is None:
            raise ApiError(503, "Failed to get distance data")
        return apiResponse({"distance_cm": data})

@router.get("/sensors/gyro", 
    response_model=GyroResponse, 
    summary="Получить данные гироскопа", 
    description="Возвращает текущие показатели: ускорения, вращения и температуру гироскопа."
)
async def get_gyro(payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('gyro')
    if not cmd:
        raise ApiError(500, "Gyro command not initialized")

    if getattr(cmd, 'is_subscribed', False):
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

@router.get("/sensors/millis", 
    response_model=MillisResponse, 
    summary="Получить миллисекунды (uptime)", 
    description="Возвращает количество миллисекунд (uptime), прошедших с момента старта робота (контроллера)."
)
async def get_millis(payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('millis')
    if not cmd:
        raise ApiError(500, "Millis command not initialized")

    if getattr(cmd, 'is_subscribed', False):
        data = cmd.last_data
        if data is None:
            raise ApiError(503, "Millis data not available")
        return apiResponse({"millis": data})
    else:
        data = cmd.execute()
        if data is None:
            raise ApiError(503, "Failed to get millis data")
        return apiResponse({"millis": data})

@router.post("/commands/ping", 
    response_model=CommandSuccessResponse, 
    summary="Пинг робота", 
    description="Отправить команду ping контроллеру, чтобы убедиться в работоспособности соединения."
)
async def ping_robot(payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('ping')
    if not cmd:
        raise ApiError(500, "Ping command not initialized")

    result = cmd.execute()
    return apiResponse({"command": "ping", "success": result is not None})

@router.post("/commands/motors", 
    response_model=CommandSuccessResponse, 
    summary="Управление моторами", 
    description="Позволяет задавать скорость, направление движения и торможение для правого или левого (или обоих) моторов."
)
async def control_motors(req: MotorsCommandRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    command = req.command
    try:
        result = False
        if command == "set_speed":
            motor_mask = req.motor_mask if req.motor_mask is not None else cmd.MOTOR_BOTH
            speed_left = req.speed_left or 0
            speed_right = req.speed_right or 0
            result = cmd.set_speed(motor_mask, speed_left, speed_right)
        elif command == "set_direction":
            motor_mask = req.motor_mask if req.motor_mask is not None else cmd.MOTOR_BOTH
            direction_left = req.direction_left if req.direction_left is not None else cmd.DIRECTION_STOP
            direction_right = req.direction_right if req.direction_right is not None else cmd.DIRECTION_STOP
            result = cmd.set_direction(motor_mask, direction_left, direction_right)
        elif command == "move_forward":
            speed = req.speed or 150
            result = cmd.move_forward(speed)
        elif command == "move_backward":
            speed = req.speed or 150
            result = cmd.move_backward(speed)
        elif command == "turn_left":
            speed = req.speed or 150
            result = cmd.turn_left(speed)
        elif command == "turn_right":
            speed = req.speed or 150
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

@router.post("/commands/servo", 
    response_model=CommandSuccessResponse, 
    summary="Управление сервоприводом", 
    description="Позволяет управлять конкретным каналом сервопривода (моментальное или плавное движение до нужного угла)."
)
async def control_servo(req: ServoCommandRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('servo')
    if not cmd:
        raise ApiError(500, "Servo command not initialized")

    command = req.command
    try:
        result = False
        if command == "move_immediate":
            result = cmd.move_immediate(req.channel, req.angle)
        elif command == "move_smooth":
            step_delay = req.step_delay or 50
            result = cmd.move_smooth_high(req.channel, req.angle, step_delay)
        else:
            raise ApiError(400, f"Unknown command: {command}")

        return apiResponse({"command": command, "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.get("/connection/status", 
    response_model=ConnectionStatusResponse, 
    summary="Статус соединения ComLink RT", 
    description="Возвращает состояние соединения с микроконтроллером, порт и список активных подписок на датчики."
)
async def get_connection_status(payload: dict = login_required()):
    connected = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)

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

app.include_router(router)