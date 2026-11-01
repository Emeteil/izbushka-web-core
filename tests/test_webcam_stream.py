import ast
import asyncio
import statistics
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import anyio
import httpx
import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from api.schemas.webcam import WebcamQualityRequest


@pytest.fixture
def stream_state():
    path = Path(__file__).resolve().parents[1] / "api" / "webcam_api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if getattr(node, "name", None) in {
        "generate_frames", "webcam_snapshot", "publish_frame",
    }]
    for function in functions:
        function.decorator_list = []
    namespace = {
        "asyncio": asyncio,
        "time": time,
        "np": SimpleNamespace(mean=statistics.mean),
        "frame_lock": threading.Lock(),
        "current_frame_bytes": None,
        "last_frame_time": 0,
        "frame_sequence": 0,
        "frame_quality": 30,
        "current_frame": None,
        "video_quality": {"fps": 1000, "auto_adjust": True, "network_adaptation": True,
                          "quality": 30, "min_quality": 1},
        "frame_stats": {"stream_intervals": []},
        "Response": Response,
        "HTTPException": HTTPException,
        "Query": Query,
        "login_required": lambda *_: None,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", [None, b"stale"])
async def test_waiting_streams_do_not_block_static_files(stream_state, tmp_path, frame):
    stream_state["current_frame_bytes"] = frame
    (tmp_path / "socketio_mock.js").write_text("const ready = true;", encoding="utf-8")
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=tmp_path))
    streams = [stream_state["generate_frames"]() for _ in range(60)]
    tasks = [asyncio.create_task(anext(stream)) for stream in streams]
    limiter = anyio.to_thread.current_default_thread_limiter()
    previous = limiter.total_tokens
    limiter.total_tokens = 1
    try:
        await asyncio.sleep(0.03)
        assert not any(task.done() for task in tasks)
        assert stream_state["frame_lock"].acquire(blocking=False)
        stream_state["frame_lock"].release()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await asyncio.wait_for(client.get("/static/socketio_mock.js"), timeout=1)
        assert response.status_code == 200
        assert response.text == "const ready = true;"
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for stream in streams:
            await stream.aclose()
        limiter.total_tokens = previous


@pytest.mark.asyncio
async def test_new_frame_delivered_after_wait(stream_state):
    stream = stream_state["generate_frames"]()
    task = asyncio.create_task(anext(stream))
    try:
        await asyncio.sleep(0.02)
        stream_state["current_frame_bytes"] = b"jpeg"
        stream_state["last_frame_time"] = time.time()
        frame = await asyncio.wait_for(task, timeout=1)
        assert frame == b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg\r\n"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await stream.aclose()


@pytest.mark.asyncio
async def test_slow_history_does_not_freeze_stream_and_duplicate_wait_can_be_cancelled(stream_state):
    stream_state["current_frame_bytes"] = b"jpeg"
    stream_state["last_frame_time"] = time.time()
    stream_state["video_quality"]["auto_adjust"] = True
    stream_state["frame_stats"]["stream_intervals"] = [0.1] * 5
    stream = stream_state["generate_frames"]()
    frame = await asyncio.wait_for(anext(stream), timeout=1)
    assert b"jpeg" in frame
    task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    await stream.aclose()


@pytest.mark.asyncio
async def test_stream_clients_do_not_change_quality_or_capture_statistics(stream_state):
    stream_state["publish_frame"](b"first", quality=30)
    streams = [stream_state["generate_frames"]() for _ in range(3)]
    try:
        first = await asyncio.gather(*(anext(stream) for stream in streams))
        assert all(b"first" in frame for frame in first)
        assert stream_state["frame_stats"]["stream_intervals"] == []
        stream_state["publish_frame"](b"newest", quality=30)
        latest = await asyncio.gather(*(anext(stream) for stream in streams))
        assert all(b"newest" in frame for frame in latest)
        assert len(stream_state["frame_stats"]["stream_intervals"]) == 1
        assert stream_state["video_quality"]["quality"] == 30
    finally:
        for stream in streams:
            await stream.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("frame,age,status", [(None, 0, 404), (b"stale", 2, 503)])
async def test_snapshot_rejects_missing_or_stale_frames(stream_state, frame, age, status):
    stream_state["current_frame_bytes"] = frame
    stream_state["last_frame_time"] = time.time() - age
    with pytest.raises(HTTPException) as error:
        await stream_state["webcam_snapshot"](quality=None, after=None)
    assert error.value.status_code == status


@pytest.mark.asyncio
async def test_snapshot_unchanged_frame_has_no_body(stream_state):
    stream_state["publish_frame"](b"jpeg", quality=30)
    response = await stream_state["webcam_snapshot"](quality=None, after=1)
    assert response.status_code == 204
    assert response.body == b""
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-sequence"] == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", [None, 30, 95])
async def test_snapshot_default_and_quality_ceiling_reuse_encoded_frame(stream_state, requested):
    stream_state["publish_frame"](b"jpeg", quality=30)
    response = await stream_state["webcam_snapshot"](quality=requested, after=None)
    assert response.body == b"jpeg"
    assert response.headers["x-webcam-quality"] == "30"


@pytest.mark.asyncio
async def test_snapshot_encoding_runs_outside_event_loop_and_preserves_base_quality(stream_state):
    main_thread = threading.get_ident()
    calls = []

    def encode(frame, data, quality):
        calls.append((threading.get_ident(), frame, data, quality))
        return b"small jpeg"

    stream_state["encode_snapshot"] = encode
    stream_state["publish_frame"](b"jpeg", frame="raw", quality=30)
    response = await stream_state["webcam_snapshot"](quality=10, after=None)
    assert response.body == b"small jpeg"
    assert calls[0][0] != main_thread
    assert calls[0][1:] == ("raw", b"jpeg", 10)
    assert response.headers["x-webcam-quality"] == "30"
    assert stream_state["video_quality"]["quality"] == 30


@pytest.mark.asyncio
async def test_snapshot_http_query_validation_and_headers(stream_state):
    app = FastAPI()
    app.add_api_route('/snapshot', stream_state["webcam_snapshot"], methods=['GET'])
    stream_state["publish_frame"](b"jpeg", quality=30)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get('/snapshot?quality=95')
        assert response.status_code == 200
        assert response.content == b"jpeg"
        for query in ('quality=0', 'quality=96', 'after=-1', 'quality=invalid'):
            response = await client.get('/snapshot?' + query)
            assert response.status_code == 422


@pytest.mark.parametrize("dimensions", [{"width": 0}, {"height": -1}, {"width": 1921}, {"height": 1081}])
def test_invalid_camera_dimensions_are_rejected(dimensions):
    with pytest.raises(ValidationError):
        WebcamQualityRequest(**dimensions)


def test_existing_ultra_low_resolution_is_supported():
    request = WebcamQualityRequest(width=70, height=70)
    assert (request.width, request.height) == (70, 70)
