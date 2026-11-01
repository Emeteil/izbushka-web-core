from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from authorization import login_required
from utils.api_response import apiResponse
import cv2
import asyncio
import threading
import atexit
import time
import numpy as np
import secrets
from starlette.background import BackgroundTask
from settings import app, settings, transport_bus
from api.schemas.webcam import WebcamStatusResponse, WebcamQualityResponse, WebcamQualityRequest, WebcamStreamFeedback

router = APIRouter(prefix="/api/webcam", tags=["Webcam"])
stream_sessions = {}

current_frame = None
current_frame_bytes = None
frame_sequence = 0
frame_quality = 20
last_frame_time = 0
frame_lock = threading.Lock()
capture_thread = None
stop_capture = False

video_quality = {
    "quality": 20,
    "width": 320,
    "height": 240,
    "fps": 15,
    "auto_adjust": False,
    "min_quality": 1,
    "max_quality": 95,
    "network_adaptation": False
}

frame_stats = {
    "capture_times": [],
    "encode_times": [],
    "stream_intervals": [],
    "target_fps": 15,
    "last_adjustment": 0,
    "adjustment_interval": 2.0
}

encode_params = [cv2.IMWRITE_JPEG_OPTIMIZE, 1]


def publish_frame(frame_bytes, frame=None, quality=None):
    global current_frame, current_frame_bytes, last_frame_time, frame_sequence, frame_quality
    now = time.time()
    with frame_lock:
        if last_frame_time and now > last_frame_time:
            frame_stats["stream_intervals"].append(now - last_frame_time)
            frame_stats["stream_intervals"] = frame_stats["stream_intervals"][-100:]
        current_frame = frame
        current_frame_bytes = frame_bytes
        last_frame_time = now
        frame_sequence += 1
        frame_quality = quality


def _inject_virtual_frame(frame_bytes: bytes):
    publish_frame(frame_bytes)


def encode_snapshot(frame, frame_bytes, quality):
    if frame is None:
        frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=503, detail="invalid camera frame")
    success, buffer = cv2.imencode('.jpg', frame, encode_params + [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise HTTPException(status_code=503, detail="camera encoding failed")
    return buffer.tobytes()


def capture_frames():
    vl_in_bus = transport_bus.get("virtual_link") is not None
    is_virtual = vl_in_bus and settings.get("transport", {}).get("virtual_link", {}).get("virtual_camera", False)
    if is_virtual:
        while not stop_capture:
            time.sleep(1.0)
        return

    dev = settings.get("webcam", {}).get("device", 0)
    cap = cv2.VideoCapture(dev, cv2.CAP_V4L2) if isinstance(dev, str) else cv2.VideoCapture(dev)

    capture_fps = video_quality["fps"]
    cap.set(cv2.CAP_PROP_FPS, capture_fps)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, video_quality["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, video_quality["height"])
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    while not stop_capture:
        start_time = time.monotonic()
        frame_settings = video_quality.copy()
        target_frame_time = 1.0 / frame_settings["fps"]
        if capture_fps != frame_settings["fps"]:
            capture_fps = frame_settings["fps"]
            cap.set(cv2.CAP_PROP_FPS, capture_fps)

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        if frame_settings["width"] and frame_settings["height"]:
            frame = cv2.resize(frame, (frame_settings["width"], frame_settings["height"]))

        encode_start = time.monotonic()

        current_quality = frame_settings["quality"]
        encode_params_with_quality = encode_params + [cv2.IMWRITE_JPEG_QUALITY, int(current_quality)]

        ret, buffer = cv2.imencode('.jpg', frame, encode_params_with_quality)
        encode_time = time.monotonic() - encode_start

        if ret:
            publish_frame(buffer.tobytes(), frame, current_quality)

        frame_stats["capture_times"].append(time.monotonic() - start_time)
        frame_stats["encode_times"].append(encode_time)
        if len(frame_stats["capture_times"]) > 100:
            frame_stats["capture_times"] = frame_stats["capture_times"][-100:]
            frame_stats["encode_times"] = frame_stats["encode_times"][-100:]

        elapsed = time.monotonic() - start_time
        sleep_time = max(0, target_frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)

    cap.release()


async def generate_frames(session=None):
    last_yield_time = 0
    last_sequence = -1

    while True:
        current_time = time.monotonic()
        base = video_quality.copy()
        fps = base["fps"]
        quality = base["quality"]
        if session:
            if base["network_adaptation"]:
                fps = min(fps, session.get("fps", fps))
            if base["auto_adjust"]:
                quality = max(base["min_quality"], min(quality, session.get("quality", quality)))
        target_interval = 1.0 / fps

        elapsed_since_last = current_time - last_yield_time
        if elapsed_since_last < target_interval:
            sleep_time = target_interval - elapsed_since_last
            await asyncio.sleep(max(0.001, sleep_time))
            continue

        with frame_lock:
            frame_data = current_frame_bytes
            frame_age = time.time() - last_frame_time
            sequence = frame_sequence
            frame = current_frame
            source_quality = frame_quality

        if frame_data is None or frame_age > 0.5 or sequence == last_sequence:
            await asyncio.sleep(0.01)
            continue

        if quality != source_quality and (source_quality is not None or quality < base["quality"]):
            frame_data = await asyncio.to_thread(encode_snapshot, frame, frame_data, quality)
        last_sequence = sequence
        last_yield_time = time.monotonic()
        intervals = frame_stats["stream_intervals"][-10:]
        capture_fps = min(base["fps"], 1 / max(0.001, sum(intervals) / len(intervals))) if intervals else base["fps"]
        headers = (
            f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame_data)}\r\n'
            f'X-Frame-Sequence: {sequence}\r\nX-Frame-Time: {last_yield_time:.6f}\r\n'
            f'X-Webcam-Quality: {base["quality"]}\r\nX-Webcam-Fps: {base["fps"]}\r\n'
            f'X-Capture-Fps: {capture_fps:.3f}\r\nX-Stream-Fps: {fps:.3f}\r\n'
            f'X-Webcam-Auto: {int(base["auto_adjust"])}\r\n'
            f'X-Webcam-Network: {int(base["network_adaptation"])}\r\n\r\n'
        ).encode("ascii")
        yield headers + frame_data + b'\r\n'


async def generate_session_frames(stream_id):
    try:
        async for frame in generate_frames(stream_sessions[stream_id]):
            yield frame
    finally:
        stream_sessions.pop(stream_id, None)


def release_stream(stream_id):
    stream_sessions.pop(stream_id, None)


def start_webcam_capture():
    global capture_thread, stop_capture
    if capture_thread is None or not capture_thread.is_alive():
        stop_capture = False
        capture_thread = threading.Thread(target=capture_frames, daemon=True)
        capture_thread.start()


def stop_webcam_capture():
    global stop_capture
    stop_capture = True
    if capture_thread:
        capture_thread.join(timeout=1.0)


def restart_webcam_capture():
    stop_webcam_capture()
    start_webcam_capture()


start_webcam_capture()
atexit.register(stop_webcam_capture)

is_virtual_camera = settings.get("transport", {}).get("virtual_link", {}).get("virtual_camera", False)
if is_virtual_camera:
    vl = transport_bus.get("virtual_link")
    if vl and hasattr(vl, 'on_frame_callback'):
        vl.on_frame_callback = _inject_virtual_frame


@router.get("/stream",
            summary="Получить видеопоток с камеры",
            description="Возвращает стрим кадров с веб-камеры в формате multipart/x-mixed-replace (MJPEG). "
                        "Требует авторизации (через параметр токена)."
            )
async def webcam_stream(payload: dict = login_required("args")):
    stream_id = secrets.token_urlsafe(18)
    stream_sessions[stream_id] = {"user_id": payload["user_id"]}
    return StreamingResponse(generate_session_frames(stream_id), media_type='multipart/x-mixed-replace; boundary=frame',
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "X-Stream-Id": stream_id},
                             background=BackgroundTask(release_stream, stream_id))


@router.post("/stream/{stream_id}/feedback")
async def webcam_feedback(stream_id: str, req: WebcamStreamFeedback, payload: dict = login_required()):
    session = stream_sessions.get(stream_id)
    if session is None or session["user_id"] != payload["user_id"]:
        raise HTTPException(status_code=404, detail="video stream not found")
    session.update(quality=req.quality, fps=req.fps)
    return Response(status_code=204)


@router.get("/snapshot",
            summary="Получить один кадр с камеры",
            description="Возвращает свежий JPEG. quality ограничивает качество только этого запроса; "
                        "after с номером текущего кадра возвращает 204, пока новый кадр не захвачен. "
                        "Требует авторизации (через параметр токена)."
            )
async def webcam_snapshot(payload: dict = login_required("args"),
                          quality: int = Query(None, ge=1, le=95), after: int = Query(None, ge=0)):
    with frame_lock:
        frame_data = current_frame_bytes
        frame = current_frame
        sequence = frame_sequence
        age = time.time() - last_frame_time
        source_quality = frame_quality
    if frame_data is None:
        raise HTTPException(status_code=404, detail="no frame available yet")
    if age > 0.5:
        raise HTTPException(status_code=503, detail="camera frame is stale")
    headers = {
        "Cache-Control": "no-store",
        "X-Frame-Sequence": str(sequence),
        "X-Webcam-Quality": str(video_quality["quality"]),
        "X-Webcam-Fps": str(video_quality["fps"]),
        "X-Webcam-Auto": str(int(video_quality["auto_adjust"])),
        "X-Webcam-Network": str(int(video_quality["network_adaptation"])),
    }
    if after == sequence:
        return Response(status_code=204, headers=headers)
    if quality is not None:
        quality = max(video_quality["min_quality"], min(video_quality["quality"], quality))
        if quality != source_quality:
            frame_data = await asyncio.to_thread(encode_snapshot, frame, frame_data, quality)
    return Response(content=frame_data, media_type="image/jpeg", headers=headers)


@router.get("/status",
            response_model=WebcamStatusResponse,
            summary="Статус веб-камеры",
            description="Возвращает текущий статус захвата, доступность кадров и возраст последнего кадра."
            )
async def webcam_status(payload: dict = login_required()):
    return apiResponse({
        "status": "running" if capture_thread and capture_thread.is_alive() else "stopped",
        "frame_available": current_frame_bytes is not None,
        "last_frame_age": time.time() - last_frame_time if last_frame_time > 0 else None,
        "current_quality": video_quality["quality"],
        "actual_fps": (
            1.0 / np.mean(frame_stats["stream_intervals"][-10:])
            if len(frame_stats["stream_intervals"]) >= 10 else None
        )
    })


@router.get("/quality",
            response_model=WebcamQualityResponse,
            summary="Получить настройки качества камеры",
            description="Возвращает текущие настройки качества видеопотока "
                        "и статистику производительности (FPS, задержку и т.д.)."
            )
async def get_webcam_quality(payload: dict = login_required()):
    stats = {
        "avg_capture_time": float(np.mean(frame_stats["capture_times"][-10:])) if frame_stats["capture_times"] else 0.0,  # noqa: E501
        "avg_encode_time": float(np.mean(frame_stats["encode_times"][-10:])) if frame_stats["encode_times"] else 0.0,  # noqa: E501
        "avg_stream_interval": float(np.mean(frame_stats["stream_intervals"][-10:])) if frame_stats["stream_intervals"] else 0.0,  # noqa: E501
        "target_fps": frame_stats["target_fps"]
    }
    return apiResponse({
        "quality": video_quality,
        "statistics": stats
    })


@router.put("/quality",
            response_model=WebcamQualityResponse,
            summary="Установить настройки качества камеры",
            description="Изменяет качество, разрешение и FPS без перезапуска захвата. "
                        "Автоподстройка JPEG и FPS выполняется отдельно в каждом браузере."
            )
async def set_webcam_quality(req: WebcamQualityRequest, payload: dict = login_required()):
    if req.quality is not None:
        video_quality["quality"] = max(video_quality["min_quality"], min(video_quality["max_quality"], req.quality))

    if req.width is not None:
        video_quality["width"] = req.width

    if req.height is not None:
        video_quality["height"] = req.height

    if req.fps is not None:
        video_quality["fps"] = max(1, min(60, req.fps))
        frame_stats["target_fps"] = video_quality["fps"]

    if req.auto_adjust is not None:
        video_quality["auto_adjust"] = req.auto_adjust

    if req.network_adaptation is not None:
        video_quality["network_adaptation"] = req.network_adaptation

    if any(var is not None for var in [req.quality, req.width, req.height, req.fps]):
        for key in frame_stats:
            if isinstance(frame_stats[key], list):
                frame_stats[key] = []

    return apiResponse({
        "quality": video_quality,
        "message": "Video quality settings updated"
    })


@router.post("/stats/reset",
             summary="Сбросить статистику производительности",
             description="Очищает собранную статистику задержек кадров, захвата и кодирования."
             )
async def reset_stats(payload: dict = login_required()):
    for key in frame_stats:
        if isinstance(frame_stats[key], list):
            frame_stats[key] = []
    frame_stats["last_adjustment"] = 0

    return apiResponse({
        "message": "Statistics reset",
        "quality": video_quality
    })

app.include_router(router)
