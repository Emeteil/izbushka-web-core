from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import secrets
import yaml, os
import logging

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

if settings.get("load_dotenv"):
    load_dotenv()

for env in settings.get("environment_variables", []):
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

app = FastAPI(
    debug=settings.get('debug', False),
    title="WEB Core Избушки",
    description="Frontend + Backend для Избушки",
    version="1.0.0"
)

if "cors" in settings:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings["cors"].get("allow_origins", ["*"]),
        allow_credentials=settings["cors"].get("allow_credentials", True),
        allow_methods=settings["cors"].get("allow_methods", ["*"]),
        allow_headers=settings["cors"].get("allow_headers", ["*"]),
    )

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

log_dir = settings.get("logging", {}).get("log_dir", "logs")
os.makedirs(log_dir, exist_ok=True)
log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
formatter = logging.Formatter(log_format)
log_level = logging.INFO if not settings.get("debug") else logging.DEBUG
log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")
log_filepath = os.path.join(log_dir, log_filename)

logger = logging.getLogger("fastapi")
logger.setLevel(log_level)
file_handler = logging.FileHandler(log_filepath)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(log_level)
uvicorn_file_handler = logging.FileHandler(log_filepath)
uvicorn_file_handler.setFormatter(formatter)
uvicorn_logger.addHandler(uvicorn_file_handler)

settings["SECRET_KEY"] = settings.get("flask_secret", secrets.token_urlsafe(32))
settings["MASTER_TOKEN"] = os.environ.get("MASTER_TOKEN", secrets.token_urlsafe(32))

current_emotion = "neutral"