from pydantic import BaseModel, Field
from typing import Optional

class DistanceResponse(BaseModel):
    distance_cm: float = Field(..., description="Измеренная дистанция в сантиметрах")

class GyroData(BaseModel):
    x: float = Field(..., description="Значение по оси X")
    y: float = Field(..., description="Значение по оси Y")
    z: float = Field(..., description="Значение по оси Z")

class GyroResponse(BaseModel):
    accel: GyroData = Field(..., description="Данные акселерометра")
    gyro: GyroData = Field(..., description="Данные гироскопа")
    temperature: float = Field(..., description="Температура в градусах Цельсия")

class MillisResponse(BaseModel):
    millis: int = Field(..., description="Миллисекунды с момента старта робота")

class CommandSuccessResponse(BaseModel):
    command: str = Field(..., description="Выполненная команда")
    success: bool = Field(..., description="True, если команда выполнена успешно")

class MotorsCommandRequest(BaseModel):
    command: str = Field(..., description="Команда для моторов: set_speed, set_direction, move_forward, move_backward, turn_left, turn_right, stop, brake")
    motor_mask: Optional[int] = Field(None, description="Маска моторов (1 - левый, 2 - правый, 3 - оба)")
    speed_left: Optional[int] = Field(None, description="Скорость для левого мотора (0-255)")
    speed_right: Optional[int] = Field(None, description="Скорость для правого мотора (0-255)")
    direction_left: Optional[int] = Field(None, description="Направление левого мотора (1 - вперед, -1 - назад, 0 - стоп)")
    direction_right: Optional[int] = Field(None, description="Направление правого мотора (1 - вперед, -1 - назад, 0 - стоп)")
    speed: Optional[int] = Field(None, description="Скорость для команд движения (0-255)")

class ServoCommandRequest(BaseModel):
    command: str = Field(..., description="Команда для сервопривода: move_immediate, move_smooth")
    channel: int = Field(0, description="Канал сервопривода (0-15)")
    angle: int = Field(..., description="Целевой угол в градусах (0-180)")
    step_delay: Optional[int] = Field(50, description="Задержка на шаг в миллисекундах для плавного движения")

class ConnectionStatusResponse(BaseModel):
    connected: bool = Field(..., description="True, если подключение к ComLink RT активно")
    port: str | None = Field(None, description="Используемый последовательный порт")
    subscriptions: dict[str, bool] = Field(..., description="Текущие активные подписки на данные")
