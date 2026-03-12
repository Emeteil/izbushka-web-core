from pydantic import BaseModel, Field
from typing import Optional

class WebcamStatusResponse(BaseModel):
    status: str = Field(..., description="Текущий статус захвата камеры (running, stopped)")
    frame_available: bool = Field(..., description="True, если кадр доступен в буфере")
    last_frame_age: Optional[float] = Field(None, description="Возраст последнего сохраненного кадра в секундах")
    current_quality: int = Field(..., description="Текущее качество JPEG (1-95)")
    actual_fps: Optional[float] = Field(None, description="Фактическая частота кадров в секунду")

class WebcamStats(BaseModel):
    avg_capture_time: float = Field(..., description="Среднее время чтения кадра с камеры (в секундах)")
    avg_encode_time: float = Field(..., description="Среднее время кодирования кадра в JPEG (в секундах)")
    avg_stream_interval: float = Field(..., description="Средний интервал между выдаваемыми кадрами (в секундах)")
    target_fps: int = Field(..., description="Целевая частота кадров")

class WebcamQualitySettings(BaseModel):
    quality: int = Field(..., description="Базовое качество JPEG (1-95)")
    width: int = Field(..., description="Ширина видеопотока")
    height: int = Field(..., description="Высота видеопотока")
    fps: int = Field(..., description="Целевая частота кадров")
    auto_adjust: bool = Field(..., description="Автоматическая настройка качества на основе сети")
    min_quality: int = Field(..., description="Минимальное качество для автонастройки")
    max_quality: int = Field(..., description="Максимальное качество для автонастройки")
    network_adaptation: bool = Field(..., description="Использовать адаптацию к сетевым условиям")

class WebcamQualityResponse(BaseModel):
    quality: WebcamQualitySettings = Field(..., description="Текущие настройки качества веб-камеры")
    statistics: Optional[WebcamStats] = Field(None, description="Текущая статистика производительности")
    message: Optional[str] = Field(None, description="Сообщение о статусе выполнения запроса")

class WebcamQualityRequest(BaseModel):
    quality: Optional[int] = Field(None, ge=1, le=95, description="Новый уровень качества JPEG (1-95)")
    width: Optional[int] = Field(None, description="Новая ширина видео")
    height: Optional[int] = Field(None, description="Новая высота видео")
    fps: Optional[int] = Field(None, ge=1, le=60, description="Новая целевая частота кадров (1-60)")
    auto_adjust: Optional[bool] = Field(None, description="Включить или выключить автоматическую настройку качества")
    network_adaptation: Optional[bool] = Field(None, description="Включить или выключить адаптацию к сети")
