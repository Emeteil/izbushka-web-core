from contextlib import asynccontextmanager
import asyncio
from settings import com_link_connection, com_link_commands, transport_bus
from services.sensor_service import format_distance
from utils.connection_manager import manager
import api.voice_broadcast
import api.voice_link
import api.webcam_api
import api.com_link_rt_api
import api.authorization
import api.websockets
import api.emotions_api
import events  # noqa: F401
import api.admin  # noqa: F401
from fastapi import Request
from fastapi.responses import RedirectResponse
import uvicorn
import webbrowser
import threading
import time
import logging

from settings import app, settings, templates
from authorization import is_logged
from utils.tracing import trace_scope, get_trace_id

_request_logger = logging.getLogger("http")


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Trace-Id")
    started = time.perf_counter()
    with trace_scope(incoming):
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        trace_id = get_trace_id() or "-"
        response.headers["X-Trace-Id"] = trace_id
        _request_logger.info(
            "http.request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response


@asynccontextmanager
async def lifespan(app):
    loop = asyncio.get_event_loop()

    def on_millis_data(millis):
        if millis is not None:
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "sensor.data", "data": {"millis": {"millis": millis}}}),
                    loop
                )

    def on_distance_data(values):
        payload = format_distance(values)
        if payload is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"event": "sensor.data", "data": {"distance": payload}}),
                loop
            )

    sensor_callbacks = {"millis": on_millis_data, "distance": on_distance_data}

    if com_link_connection and com_link_commands:
        for name, callback in sensor_callbacks.items():
            try:
                com_link_commands[name].subscribe(callback)
            except Exception as e:
                print(f"Failed to subscribe to {name}: {e}")
    else:
        vl = transport_bus.get("virtual_link")
        if vl and hasattr(vl, 'subscribe'):
            for name, callback in sensor_callbacks.items():
                try:
                    vl.subscribe(name, callback)
                except Exception as e:
                    print(f"Failed to subscribe to {name} via virtual link: {e}")

    yield

    if com_link_connection:
        try:
            com_link_connection.disconnect()
        except Exception as e:
            print(f"Error disconnecting ComLink: {e}")

    if transport_bus:
        try:
            transport_bus.stop_all()
        except Exception as e:
            print(f"Error stopping transport bus: {e}")

app.router.lifespan_context = lifespan


@app.get("/", include_in_schema=False)
async def mainPage(request: Request):
    logged, _ = await is_logged(request, "args")
    logged2, _ = await is_logged(request, "cookies")
    if not logged and not logged2:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "index.html")


@app.get("/login", include_in_schema=False)
async def loginPage(request: Request):
    logged, payload = await is_logged(request, "cookies")
    if logged:
        return RedirectResponse(url="/control", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@app.get("/control", include_in_schema=False)
async def controlPage(request: Request):
    logged, _ = await is_logged(request, "cookies")
    if not logged:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "control.html")


@app.get("/operator", include_in_schema=False)
async def operatorPage(request: Request):
    logged, _ = await is_logged(request, "cookies")
    if not logged:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "operator.html")


@app.get("/admin", include_in_schema=False)
async def adminPage(request: Request):
    logged, _ = await is_logged(request, "cookies")
    if not logged:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "admin_panel.html")


def open_browser():
    time.sleep(1.5)
    master_token = settings.get("MASTER_TOKEN")
    host = settings.get("host", "127.0.0.1")
    port = settings.get("port", 8080)
    url = f"http://{host}:{port}?token={master_token}"
    webbrowser.open(url)


if __name__ == "__main__":
    if settings.get("open_browser_on_start", True):
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "main:app",
        host=settings.get("host", "127.0.0.1"),
        port=settings.get("port", 8080),
        reload=settings.get("debug", False)
    )
