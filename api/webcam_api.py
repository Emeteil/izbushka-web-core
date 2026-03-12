from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from authorization import login_required
from utils.api_response import apiResponse
import cv2
import threading
import atexit
import time
import numpy as np
from settings import app
from api.schemas.webcam import WebcamStatusResponse, WebcamQualityResponse, WebcamQualityRequest

router = APIRouter(prefix="/api/webcam", tags=["Webcam"])

current_frame = None
current_frame_bytes = None
last_frame_time = 0
frame_lock = threading.Lock()
capture_thread = None
stop_capture = False

video_quality = {
    "quality": 30,
    "width": 640,
    "height": 480,
    "fps": 23,
    "auto_adjust": False,
    "min_quality": 1,
    "max_quality": 95,
    "network_adaptation": False
}

frame_stats = {
    "capture_times": [],
    "encode_times": [],
    "stream_intervals": [],
    "target_fps": 23,
    "last_adjustment": 0,
    "adjustment_interval": 2.0
}

encode_params = [cv2.IMWRITE_JPEG_OPTIMIZE, 1]

def calculate_adaptive_quality(network_delay):
    if not video_quality["network_adaptation"]:
        return video_quality["quality"]
    
    base_delay = 0.1
    max_delay = 1.0
    
    if network_delay <= base_delay:
        return video_quality["max_quality"]
    elif network_delay >= max_delay:
        return video_quality["min_quality"]
    else:
        ratio = (network_delay - base_delay) / (max_delay - base_delay)
        quality = video_quality["max_quality"] - ratio * (video_quality["max_quality"] - video_quality["min_quality"])
        return max(video_quality["min_quality"], min(video_quality["max_quality"], int(quality)))

def capture_frames():
    global current_frame, stop_capture, current_frame_bytes, last_frame_time
    cap = cv2.VideoCapture(0)
    
    cap.set(cv2.CAP_PROP_FPS, video_quality["fps"])
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, video_quality["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, video_quality["height"])
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    target_frame_time = 1.0 / video_quality["fps"]
    last_capture_time = time.time()
    
    while not stop_capture:
        start_time = time.time()
        
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        if video_quality["width"] and video_quality["height"]:
            frame = cv2.resize(frame, (video_quality["width"], video_quality["height"]))
        
        encode_start = time.time()
        
        current_quality = video_quality["quality"]
        if video_quality["auto_adjust"] and len(frame_stats["stream_intervals"]) > 5:
            avg_interval = np.mean(frame_stats["stream_intervals"][-5:])
            current_quality = calculate_adaptive_quality(avg_interval - target_frame_time)
        
        encode_params_with_quality = encode_params + [cv2.IMWRITE_JPEG_QUALITY, int(current_quality)]
        
        ret, buffer = cv2.imencode('.jpg', frame, encode_params_with_quality)
        encode_time = time.time() - encode_start
        
        if ret:
            with frame_lock:
                current_frame_bytes = buffer.tobytes()
                last_frame_time = time.time()
        
        frame_stats["capture_times"].append(time.time() - start_time)
        frame_stats["encode_times"].append(encode_time)
        if len(frame_stats["capture_times"]) > 100:
            frame_stats["capture_times"] = frame_stats["capture_times"][-100:]
            frame_stats["encode_times"] = frame_stats["encode_times"][-100:]
        
        elapsed = time.time() - last_capture_time
        sleep_time = max(0, target_frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        last_capture_time = time.time()

    cap.release()

def generate_frames():
    global video_quality, frame_stats
    last_yield_time = time.time()
    frames_dropped = 0
    
    while True:
        current_time = time.time()
        target_interval = 1.0 / video_quality["fps"]
        
        elapsed_since_last = current_time - last_yield_time
        if elapsed_since_last < target_interval:
            sleep_time = target_interval - elapsed_since_last
            time.sleep(max(0.001, sleep_time))
            continue
        
        with frame_lock:
            if current_frame_bytes is None:
                time.sleep(0.01)
                continue
            
            frame_age = current_time - last_frame_time
            if frame_age > 0.5:
                time.sleep(0.01)
                continue
            
            frame_data = current_frame_bytes
        
        if video_quality["auto_adjust"]:
            avg_interval = np.mean(frame_stats["stream_intervals"][-5:]) if len(frame_stats["stream_intervals"]) >= 5 else target_interval
            if avg_interval > target_interval * 1.5:
                frames_dropped += 1
                continue
        
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n'
        
        now = time.time()
        frame_interval = now - last_yield_time
        frame_stats["stream_intervals"].append(frame_interval)
        if len(frame_stats["stream_intervals"]) > 100:
            frame_stats["stream_intervals"] = frame_stats["stream_intervals"][-100:]
        
        last_yield_time = now
        
        current_time = time.time()
        if video_quality["auto_adjust"] and current_time - frame_stats["last_adjustment"] > frame_stats["adjustment_interval"]:
            if len(frame_stats["stream_intervals"]) >= 10:
                avg_interval = np.mean(frame_stats["stream_intervals"])
                
                if avg_interval > target_interval * 1.2:
                    video_quality["quality"] = max(
                        video_quality["min_quality"],
                        video_quality["quality"] - 5
                    )
                elif avg_interval < target_interval * 0.8 and video_quality["quality"] < video_quality["max_quality"]:
                    video_quality["quality"] = min(
                        video_quality["max_quality"],
                        video_quality["quality"] + 5
                    )
            
            frame_stats["last_adjustment"] = current_time

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

@router.get("/stream", 
    summary="Получить видеопоток с камеры", 
    description="Возвращает стрим кадров с веб-камеры в формате multipart/x-mixed-replace (MJPEG). Требует авторизации (через параметр токена)."
)
async def webcam_stream(payload: dict = login_required("args")):
    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')

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
        "actual_fps": 1.0 / np.mean(frame_stats["stream_intervals"][-10:]) if len(frame_stats["stream_intervals"]) >= 10 else None
    })

@router.get("/quality", 
    response_model=WebcamQualityResponse, 
    summary="Получить настройки качества камеры", 
    description="Возвращает текущие настройки качества видеопотока и статистику производительности (FPS, задержку и т.д.)."
)
async def get_webcam_quality(payload: dict = login_required()):
    stats = {
        "avg_capture_time": float(np.mean(frame_stats["capture_times"][-10:])) if frame_stats["capture_times"] else 0.0,
        "avg_encode_time": float(np.mean(frame_stats["encode_times"][-10:])) if frame_stats["encode_times"] else 0.0,
        "avg_stream_interval": float(np.mean(frame_stats["stream_intervals"][-10:])) if frame_stats["stream_intervals"] else 0.0,
        "target_fps": frame_stats["target_fps"]
    }
    return apiResponse({
        "quality": video_quality,
        "statistics": stats
    })

@router.post("/quality", 
    response_model=WebcamQualityResponse, 
    summary="Установить настройки качества камеры", 
    description="Позволяет изменить настройки видеопотока (качество, разрешение, FPS, автоподстройку). При некоторых изменениях (особенно FPS) возможен перезапуск захвата кадра."
)
async def set_webcam_quality(req: WebcamQualityRequest, payload: dict = login_required()):
    global video_quality, frame_stats

    restart_required = False

    if req.quality is not None:
        video_quality["quality"] = max(video_quality["min_quality"], min(video_quality["max_quality"], req.quality))

    if req.width is not None:
        video_quality["width"] = req.width

    if req.height is not None:
        video_quality["height"] = req.height

    if req.fps is not None:
        video_quality["fps"] = max(1, min(60, req.fps))
        frame_stats["target_fps"] = video_quality["fps"]
        restart_required = True

    if req.auto_adjust is not None:
        video_quality["auto_adjust"] = req.auto_adjust

    if req.network_adaptation is not None:
        video_quality["network_adaptation"] = req.network_adaptation

    if any(var is not None for var in [req.quality, req.width, req.height, req.fps]):
        for key in frame_stats:
            if isinstance(frame_stats[key], list):
                frame_stats[key] = []

    if restart_required:
        restart_webcam_capture()

    return apiResponse({
        "quality": video_quality,
        "message": "Video quality settings updated" + (" and capture restarted" if restart_required else "")
    })

@router.get("/reset_stats", 
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