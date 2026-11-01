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
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


@pytest.fixture
def stream_state():
    path = Path(__file__).resolve().parents[1] / "api" / "webcam_api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if getattr(node, "name", None) == "generate_frames")
    namespace = {
        "asyncio": asyncio,
        "time": time,
        "np": SimpleNamespace(mean=statistics.mean),
        "frame_lock": threading.Lock(),
        "current_frame_bytes": None,
        "last_frame_time": 0,
        "video_quality": {"fps": 1000, "auto_adjust": False},
        "frame_stats": {"stream_intervals": []},
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
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
async def test_adaptive_drop_can_be_cancelled(stream_state):
    stream_state["current_frame_bytes"] = b"jpeg"
    stream_state["last_frame_time"] = time.time()
    stream_state["video_quality"]["auto_adjust"] = True
    stream_state["frame_stats"]["stream_intervals"] = [0.1] * 5
    stream = stream_state["generate_frames"]()
    task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    await stream.aclose()
