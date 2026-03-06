from authorization import login_required
from settings import *
from utils.api_response import *
from flask import Response, request
import cv2
import threading
import atexit
import time
import numpy as np

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
        
        encode_params_with_quality = encode_params + [cv2.IMWRITE_JPEG_QUALITY, current_quality]
        
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

@app.route("/api/webcam/stream")
@login_required("args")
def webcam_stream(payload):
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/webcam/status")
@login_required()
def webcam_status(payload):
    return apiResponse({
        "status": "running" if capture_thread and capture_thread.is_alive() else "stopped",
        "frame_available": current_frame_bytes is not None,
        "last_frame_age": time.time() - last_frame_time if last_frame_time > 0 else None,
        "current_quality": video_quality["quality"],
        "actual_fps": 1.0 / np.mean(frame_stats["stream_intervals"][-10:]) if len(frame_stats["stream_intervals"]) >= 10 else None
    })

@app.route("/api/webcam/quality", methods=["GET", "POST"])
@login_required()
def webcam_quality(payload):
    global video_quality, frame_stats

    if request.method == "GET":
        stats = {
            "avg_capture_time": np.mean(frame_stats["capture_times"][-10:]) if frame_stats["capture_times"] else 0,
            "avg_encode_time": np.mean(frame_stats["encode_times"][-10:]) if frame_stats["encode_times"] else 0,
            "avg_stream_interval": np.mean(frame_stats["stream_intervals"][-10:]) if frame_stats["stream_intervals"] else 0,
            "target_fps": frame_stats["target_fps"]
        }

        return apiResponse({
            "quality": video_quality,
            "statistics": stats
        })

    elif request.method == "POST":
        data = request.json
        restart_required = False

        if "quality" in data and isinstance(data["quality"], int):
            video_quality["quality"] = max(video_quality["min_quality"], min(video_quality["max_quality"], data["quality"]))

        if "width" in data and isinstance(data["width"], int):
            video_quality["width"] = data["width"]

        if "height" in data and isinstance(data["height"], int):
            video_quality["height"] = data["height"]

        if "fps" in data and isinstance(data["fps"], int):
            video_quality["fps"] = max(1, min(60, data["fps"]))
            frame_stats["target_fps"] = video_quality["fps"]
            restart_required = True

        if "auto_adjust" in data and isinstance(data["auto_adjust"], bool):
            video_quality["auto_adjust"] = data["auto_adjust"]

        if "network_adaptation" in data and isinstance(data["network_adaptation"], bool):
            video_quality["network_adaptation"] = data["network_adaptation"]

        if any(key in data for key in ["quality", "width", "height", "fps"]):
            for key in frame_stats:
                if isinstance(frame_stats[key], list):
                    frame_stats[key] = []

        if restart_required:
            restart_webcam_capture()

        return apiResponse({
            "quality": video_quality,
            "message": "Video quality settings updated" + (" and capture restarted" if restart_required else "")
        })

@app.route("/api/webcam/reset_stats")
@login_required()
def reset_stats(payload):
    for key in frame_stats:
        if isinstance(frame_stats[key], list):
            frame_stats[key] = []
    frame_stats["last_adjustment"] = 0
    
    return apiResponse({
        "message": "Statistics reset",
        "quality": video_quality
    })