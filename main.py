from fastapi import Request
from fastapi.responses import RedirectResponse
import uvicorn
import webbrowser
import threading
import time

from settings import app, settings, templates
from authorization import is_logged

import api.admin
import events
import api.emotions_api
import api.websockets
import api.authorization
import api.com_link_rt_api
import api.webcam_api
import api.voice_link
import api.voice_broadcast
from utils.connection_manager import manager
from settings import com_link_connection, com_link_commands, transport_bus
import asyncio

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    loop = asyncio.get_event_loop()

    def on_distance_data(distance):
        if distance is not None:
            d = distance if isinstance(distance, (int, float)) else distance
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "sensor.data", "data": {"distance": {"distance_cm": d}}}),
                    loop
                )

    def on_gyro_data(data):
        if data is not None:
            if isinstance(data, dict) and "accel" in data:
                gyro_payload = {
                    "accel": data.get("accel", (0, 0, 0)),
                    "gyro": data.get("gyro", (0, 0, 0)),
                    "temperature": data.get("temperature", 0)
                }
            elif com_link_commands and 'gyro' in com_link_commands:
                cmd = com_link_commands['gyro']
                gyro_payload = {
                    "accel": cmd.get_acceleration(data),
                    "gyro": cmd.get_rotation(data),
                    "temperature": cmd.get_temperature(data)
                }
            else:
                return
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "sensor.data", "data": {"gyro": gyro_payload}}),
                    loop
                )

    def on_millis_data(millis):
        if millis is not None:
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "sensor.data", "data": {"millis": {"millis": millis}}}),
                    loop
                )

    if com_link_connection and com_link_commands:
        try:
            com_link_commands['distance'].subscribe(on_distance_data)
            if 'gyro' in com_link_commands:
                com_link_commands['gyro'].subscribe(on_gyro_data)
            com_link_commands['millis'].subscribe(on_millis_data)
        except Exception as e:
            print(f"Failed to subscribe to sensors: {e}")
    else:
        vl = transport_bus.get("virtual_link")
        if vl and hasattr(vl, 'subscribe'):
            try:
                vl.subscribe("distance", on_distance_data)
                vl.subscribe("gyro", on_gyro_data)
                vl.subscribe("millis", on_millis_data)
            except Exception as e:
                print(f"Failed to subscribe via virtual link: {e}")

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
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", include_in_schema=False)
async def loginPage(request: Request):
    logged, payload = await is_logged(request, "cookies")
    if logged:
        return RedirectResponse(url="/control", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/control", include_in_schema=False)
async def controlPage(request: Request):
    logged, _ = await is_logged(request, "cookies")
    if not logged:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("control.html", {"request": request})

@app.get("/admin", include_in_schema=False)
async def adminPage(request: Request):
    logged, _ = await is_logged(request, "cookies")
    if not logged:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("admin_panel.html", {"request": request})

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