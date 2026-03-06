from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from dotenv import load_dotenv
import secrets
import yaml, os

from com_link_rt import (
    ComLinkConnection,
    PingCommand,
    DistanceCommand,
    # GyroCommand,
    MillisCommand,
    MotorsCommand,
    ServoCommand
)

with open("settings.yml", "r", encoding="utf-8") as f:
    settings = yaml.load(f, Loader=yaml.FullLoader)

if settings["load_dotenv"]:
    load_dotenv()

for env in settings["environment_variables"]:
    settings[env] = os.environ.get(env)

com_link_connection = None
com_link_commands = {}

try:
    port = settings.get("com_link_rt_port")
    if port:
        com_link_connection = ComLinkConnection(port)
        com_link_connection.connect()

        com_link_commands['ping'] = PingCommand(com_link_connection)
        com_link_commands['distance'] = DistanceCommand(com_link_connection)
        # com_link_commands['gyro'] = GyroCommand(com_link_connection)
        com_link_commands['millis'] = MillisCommand(com_link_connection)
        com_link_commands['motors'] = MotorsCommand(com_link_connection)
        com_link_commands['servo'] = ServoCommand(com_link_connection)
        
        print(f"ComLink RT connected to {port}")
    else:
        print("ComLink RT port not configured")

except Exception as e:
    print(f"Failed to initialize ComLink RT: {e}")
    com_link_connection = None

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

socketio = SocketIO(app, cors_allowed_origins="*")

if com_link_connection and com_link_commands:
    try:
        def on_distance_data(distance):
            if distance is not None:
                socketio.emit("sensor_data", {"sensor": "distance", "data": distance})

        def on_gyro_data(data):
            socketio.emit("sensor_data", {"sensor": "gyro", "data": data})

        def on_millis_data(millis):
            if millis is not None:
                socketio.emit("sensor_data", {"sensor": "millis", "data": millis})

        com_link_commands['distance'].subscribe(on_distance_data)
        # com_link_commands['gyro'].subscribe(on_gyro_data)
        com_link_commands['millis'].subscribe(on_millis_data)
    except Exception as e:
        print(f"Failed to subscribe to sensors: {e}")

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://",
)

if "json" in dir(app) and hasattr(app.json, "ensure_ascii"):
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.json.compact = False

app.config["JSON_AS_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
app.config["SECRET_KEY"] = settings.get("flask_secret", secrets.token_urlsafe(32))

app.config["MASTER_TOKEN"] = os.environ.get("MASTER_TOKEN", secrets.token_urlsafe(32))

current_emotion = "neutral"