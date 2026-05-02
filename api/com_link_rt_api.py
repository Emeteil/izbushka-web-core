from fastapi import APIRouter
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from settings import app, com_link_connection, settings, transport_bus, sensor_service
from api.schemas.com_link import (
    DistanceResponse, GyroResponse, MillisResponse, CommandSuccessResponse,
    ConnectionStatusResponse, MotorsSpeedRequest, MotorsDirectionRequest,
    MotorsMoveRequest, MotorsStopRequest, ServoAngleRequest
)

router = APIRouter(prefix="/api/robot", tags=["Robot Hardware"])

DEFAULT_MOTOR_MASK = 0x03
ALLOWED_DIRECTIONS = ("forward", "backward", "left", "right")

def _check_bus():
    if not transport_bus.has_active():
        raise ApiError(503, "No active transport subscribers")

def _require_sensor(payload, label: str):
    if payload is None:
        raise ApiError(503, f"{label} data not available")
    return payload

@router.get("/sensors/distance",
    response_model=DistanceResponse,
    summary="Получить дистанцию (в см)",
    description="Запрашивает или возвращает последние данные с датчика дистанции (в сантиметрах). Поддерживает кэширование, если датчик настроен на подписку."
)
async def get_distance(payload: dict = login_required()):
    _check_bus()
    return apiResponse(_require_sensor(sensor_service.get_distance(), "Distance"))

@router.get("/sensors/gyro",
    response_model=GyroResponse,
    summary="Получить данные гироскопа",
    description="Возвращает текущие показатели: ускорения, вращения и температуру гироскопа."
)
async def get_gyro(payload: dict = login_required()):
    _check_bus()
    return apiResponse(_require_sensor(sensor_service.get_gyro(), "Gyro"))

@router.get("/sensors/millis",
    response_model=MillisResponse,
    summary="Получить миллисекунды (uptime)",
    description="Возвращает количество миллисекунд (uptime), прошедших с момента старта робота (контроллера)."
)
async def get_millis(payload: dict = login_required()):
    _check_bus()
    return apiResponse(_require_sensor(sensor_service.get_millis(), "Millis"))

@router.post("/ping",
    response_model=CommandSuccessResponse,
    summary="Пинг робота",
    description="Отправить команду ping контроллеру, чтобы убедиться в работоспособности соединения."
)
async def ping_robot(payload: dict = login_required()):
    _check_bus()
    result = transport_bus.execute("ping", "execute")
    return apiResponse({"command": "ping", "success": result is not None})

@router.post("/motors/speed",
    response_model=CommandSuccessResponse,
    summary="Установить скорость моторов",
    description="Позволяет задавать точную скорость для правого, левого (или обоих) моторов напрямую."
)
async def set_motors_speed(req: MotorsSpeedRequest, payload: dict = login_required()):
    _check_bus()
    try:
        result = transport_bus.execute(
            "motors", "set_speed",
            motor_mask=req.motor_mask if req.motor_mask is not None else DEFAULT_MOTOR_MASK,
            speed_left=req.speed_left or 0,
            speed_right=req.speed_right or 0,
        )
        return apiResponse({"command": "set_speed", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/motors/direction",
    response_model=CommandSuccessResponse,
    summary="Установить направление моторов",
    description="Позволяет задавать направление (вперед, назад, стоп) для моторов с сохранением текущей скорости."
)
async def set_motors_direction(req: MotorsDirectionRequest, payload: dict = login_required()):
    _check_bus()
    try:
        result = transport_bus.execute(
            "motors", "set_direction",
            motor_mask=req.motor_mask if req.motor_mask is not None else DEFAULT_MOTOR_MASK,
            direction_left=req.direction_left if req.direction_left is not None else 0x00,
            direction_right=req.direction_right if req.direction_right is not None else 0x00,
        )
        return apiResponse({"command": "set_direction", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))

@router.post("/motors/move",
    response_model=CommandSuccessResponse,
    summary="Движение робота",
    description="Выполнение высокоуровневых команд движения: вперед, назад, поворот влево, поворот вправо с заданной скоростью."
)
async def move_motors(req: MotorsMoveRequest, payload: dict = login_required()):
    _check_bus()
    if req.direction not in ALLOWED_DIRECTIONS:
        raise ApiError(400, "Invalid direction")
    action = f"move_{req.direction}" if req.direction in ("forward", "backward") else f"turn_{req.direction}"
    try:
        result = transport_bus.execute("motors", action, speed=req.speed)
        return apiResponse({"command": f"move_{req.direction}", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))


@router.post("/motors/stop",
    response_model=CommandSuccessResponse,
    summary="Остановка робота",
    description="Позволяет плавно остановить робота или применить резкое торможение."
)
async def stop_motors(req: MotorsStopRequest, payload: dict = login_required()):
    _check_bus()
    action = "brake" if req.mode == "brake" else "stop_all"
    try:
        result = transport_bus.execute("motors", action)
        return apiResponse({"command": req.mode, "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))


@router.post("/servo/{channel}",
    response_model=CommandSuccessResponse,
    summary="Управление сервоприводом",
    description="Позволяет управлять конкретным каналом сервопривода (моментальное или плавное движение до нужного угла)."
)
async def control_servo(channel: int, req: ServoAngleRequest, payload: dict = login_required()):
    _check_bus()
    action = "move_smooth_high" if req.smooth else "move_immediate"
    kwargs = {"channel": channel, "angle": req.angle}
    if req.smooth:
        kwargs["step_delay_ms"] = req.step_delay
    try:
        result = transport_bus.execute("servo", action, **kwargs)
        return apiResponse({"command": "servo", "success": result})
    except ValueError as e:
        raise ApiError(400, str(e))


@router.get("/connection",
    response_model=ConnectionStatusResponse,
    summary="Статус соединения ComLink RT",
    description="Возвращает состояние соединения с микроконтроллером, порт и список активных подписок на датчики."
)
async def get_connection_status(payload: dict = login_required()):
    is_hardware = bool(com_link_connection and com_link_connection.ser and com_link_connection.ser.is_open)
    vl = transport_bus.get("virtual_link")
    is_virtual = vl is not None and vl.enabled and getattr(vl, "is_connected", False)

    return apiResponse({
        "connected": is_hardware or is_virtual,
        "port": settings.get("com_link_rt_port"),
        "transport": transport_bus.status(),
        "subscriptions": sensor_service.subscriptions_status() if (is_hardware or is_virtual) else {},
    })

app.include_router(router)