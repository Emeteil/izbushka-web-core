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

from com_link_rt import (
    ComLinkConnection,
    PingCommand,
    DistanceCommand,
    MillisCommand,
    MotorsCommand,
    ServoCommand
)
from transport import TransportBus, TransportRegistry
import transport.subscribers

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
        com_link_commands['millis'] = MillisCommand(com_link_connection)
        com_link_commands['motors'] = MotorsCommand(com_link_connection)
        com_link_commands['servo'] = ServoCommand(com_link_connection)
        
        print(f"ComLink RT connected to {port}")
    else:
        print("ComLink RT port not configured")

except Exception as e:
    print(f"Failed to initialize ComLink RT: {e}")
    com_link_connection = None

def _build_transport_bus(transport_cfg: dict) -> TransportBus:
    bus = TransportBus()

    cl_cfg = transport_cfg.get("com_link_rt", {})
    if com_link_connection and com_link_commands and cl_cfg.get("enabled", True):
        bus.add(TransportRegistry.build("com_link_rt", {**cl_cfg, "commands": com_link_commands}))
    else:
        vl_cfg = transport_cfg.get("virtual_link", {})
        if vl_cfg.get("enabled", False):
            print("ComLink RT unavailable, using virtual link as fallback")
            bus.add(TransportRegistry.build("virtual_link", vl_cfg))

    log_cfg = transport_cfg.get("console_logger", {})
    if log_cfg.get("enabled", False):
        bus.add(TransportRegistry.build("console_logger", log_cfg))

    return bus


transport_bus = _build_transport_bus(settings.get("transport", {}))
print(f"Transport bus: {[s['name'] for s in transport_bus.status()]}")

from services import SensorService, HealthService, EmotionRegistry, QuestionsLogService
import time as _time
sensor_service = SensorService(transport_bus, com_link_commands)
emotion_registry = EmotionRegistry.from_yaml(settings.get("emotions_config_path", "emotions.yml"))
questions_log = QuestionsLogService(
    file_path=settings.get("questions_log_path", "database/questions.json"),
    max_entries=settings.get("questions_log_max_entries", 5000),
)
health_service = HealthService(
    transport_bus=transport_bus,
    sensor_service=sensor_service,
    com_link_connection=com_link_connection,
    com_link_port=settings.get("com_link_rt_port"),
    started_at=_time.time(),
)

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
templates = Jinja2Templates(directory="templates", auto_reload=True)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from utils.logging_setup import setup_logging

logging_cfg = settings.get("logging", {})
log_filepath = setup_logging(
    log_dir=logging_cfg.get("log_dir", "logs"),
    debug=settings.get("debug", False),
    json_format=logging_cfg.get("json_format", False),
)

settings["SECRET_KEY"] = settings.get("flask_secret", secrets.token_urlsafe(32))
settings["MASTER_TOKEN"] = os.environ.get("MASTER_TOKEN", secrets.token_urlsafe(32))

