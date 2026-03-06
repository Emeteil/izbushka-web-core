from authorization import is_logged
from settings import *

from flask import redirect, render_template, request, url_for
from utils.api_response import *
import webbrowser
import threading
import time

import api.admin
import events
import api.emotions_api
import api.websocket_handlers
import api.authorization
import api.com_link_rt_api
import api.webcam_api

@app.route("/")
def mainPage():
    logged, _ = is_logged("args")
    logged2, _ = is_logged("cookies")
    if not logged and not logged2:
        return redirect(url_for("loginPage"))
    return render_template("index.html")

@app.route("/login")
def loginPage():
    logged, payload = is_logged("cookies")
    if logged:
        return redirect(url_for("mainPage"))
    return render_template("login.html")

@app.route("/control")
def controlPage():
    logged, _ = is_logged("cookies")
    if not logged:
        return redirect(url_for("loginPage"))
    return render_template("control.html")

@app.route("/admin")
def adminPage():
    logged, _ = is_logged("cookies")
    if not logged:
        return redirect(url_for("loginPage"))
    return render_template("admin_panel.html")

def open_browser():
    time.sleep(1.5)
    master_token = app.config["MASTER_TOKEN"]
    url = f"http://{settings['host']}:{settings['port']}?token={master_token}"
    webbrowser.open(url)

if __name__ == "__main__":
    if settings.get("open_browser_on_start", True):
        threading.Thread(target=open_browser, daemon=True).start()
    
    socketio.run(
        app,
        host=settings["host"], 
        port=settings["port"],
        # debug=settings["debug"],
        debug=False,
    )