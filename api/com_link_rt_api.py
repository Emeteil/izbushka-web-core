from fastapi import APIRouter, Depends, Request
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from settings import app, com_link_connection, com_link_commands, settings
from api.schemas.com_link import (
    DistanceResponse, GyroResponse, MillisResponse, CommandSuccessResponse,
    ConnectionStatusResponse, MotorsSpeedRequest, MotorsDirectionRequest,
    MotorsMoveRequest, MotorsStopRequest, ServoAngleRequest
)

router = APIRouter(prefix="/api/robot", tags=["Robot Hardware"])

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

@router.post("/ping", 
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

@router.post("/motors/speed", 
    response_model=CommandSuccessResponse,
    summary="Установить скорость моторов",
    description="Позволяет задавать точную скорость для правого, левого (или обоих) моторов напрямую."
)
async def set_motors_speed(req: MotorsSpeedRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    try:
        motor_mask = req.motor_mask if req.motor_mask is not None else cmd.MOTOR_BOTH
        result = cmd.set_speed(motor_mask, req.speed_left or 0, req.speed_right or 0)
        return apiResponse({"command": "set_speed", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/motors/direction", 
    response_model=CommandSuccessResponse,
    summary="Установить направление моторов",
    description="Позволяет задавать направление (вперед, назад, стоп) для моторов с сохранением текущей скорости."
)
async def set_motors_direction(req: MotorsDirectionRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    try:
        motor_mask = req.motor_mask if req.motor_mask is not None else cmd.MOTOR_BOTH
        direction_left = req.direction_left if req.direction_left is not None else cmd.DIRECTION_STOP
        direction_right = req.direction_right if req.direction_right is not None else cmd.DIRECTION_STOP
        result = cmd.set_direction(motor_mask, direction_left, direction_right)
        return apiResponse({"command": "set_direction", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/motors/move", 
    response_model=CommandSuccessResponse,
    summary="Движение робота",
    description="Выполнение высокоуровневых команд движения: вперед, назад, поворот влево, поворот вправо с заданной скоростью."
)
async def move_motors(req: MotorsMoveRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    try:
        result = False
        if req.direction == "forward":
            result = cmd.move_forward(req.speed)
        elif req.direction == "backward":
            result = cmd.move_backward(req.speed)
        elif req.direction == "left":
            result = cmd.turn_left(req.speed)
        elif req.direction == "right":
            result = cmd.turn_right(req.speed)
        else:
            raise ApiError(400, "Invalid direction")
            
        return apiResponse({"command": f"move_{req.direction}", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/motors/stop", 
    response_model=CommandSuccessResponse,
    summary="Остановка робота",
    description="Позволяет плавно остановить робота или применить резкое торможение."
)
async def stop_motors(req: MotorsStopRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('motors')
    if not cmd:
        raise ApiError(500, "Motors command not initialized")

    try:
        result = False
        if req.mode == "brake":
            result = cmd.brake()
        else:
            result = cmd.stop_all()
        return apiResponse({"command": req.mode, "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/servo/{channel}", 
    response_model=CommandSuccessResponse,
    summary="Управление сервоприводом",
    description="Позволяет управлять конкретным каналом сервопривода (моментальное или плавное движение до нужного угла)."
)
async def control_servo(channel: int, req: ServoAngleRequest, payload: dict = login_required()):
    _check_connection()
    cmd = com_link_commands.get('servo')
    if not cmd:
        raise ApiError(500, "Servo command not initialized")

    try:
        if req.smooth:
            result = cmd.move_smooth_high(channel, req.angle, req.step_delay)
        else:
            result = cmd.move_immediate(channel, req.angle)

        return apiResponse({"command": "servo", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.get("/connection", 
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