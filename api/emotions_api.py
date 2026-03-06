from authorization import login_required
from settings import *
from utils.api_response import *
from flask import request

@app.route("/api/emotions/current", methods=["GET"])
def get_current_emotion():
    return apiResponse({
        "emotion": current_emotion
    })

@app.route("/api/emotions/set", methods=["POST"])
@login_required()
def set_emotion_http(payload):
    global current_emotion
    
    data = request.get_json()
    if not data or "emotion" not in data:
        raise ApiError(400, "Emotion parameter is required")
    
    emotion = data["emotion"]
    valid_emotions = settings["emotions"]["ids"]
    
    if emotion not in valid_emotions:
        raise ApiError(400, f"Invalid emotion. Must be one of: {', '.join(valid_emotions)}")
    
    current_emotion = emotion
    
    socketio.emit("emotion_changed", {
        "emotion": emotion,
        "source": "http"
    })
    
    return apiResponse({
        "message": f"Emotion changed to {emotion}",
        "emotion": emotion
    })

@app.route("/api/emotions", methods=["GET"])
@app.route("/api/emotions/list", methods=["GET"])
def list_emotions():
    return apiResponse({
        "emotions": settings["emotions"]["items"],
        "current_emotion": current_emotion
    })