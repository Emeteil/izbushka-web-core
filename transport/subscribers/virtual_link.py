from transport.base import BaseSubscriber
from typing import Any, Optional, Callable
import socket
import json
import threading
import logging
import struct
import base64

logger = logging.getLogger("transport.virtual_link")

HEADER_SIZE = 4

class VirtualLinkSubscriber(BaseSubscriber):
    def __init__(self, host: str = "127.0.0.1", port: int = 5470, timeout: float = 2.0):
        super().__init__("virtual_link")
        self._host = str(host)
        self._port = int(port)
        self._timeout = timeout
        self._server: Optional[socket.socket] = None
        self._client: Optional[socket.socket] = None
        self._write_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._accept_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._running = False
        self._subscriptions: dict[str, Callable] = {}
        self._tcp_connected = False
        self.on_frame_callback: Optional[Callable[[bytes], None]] = None

        self._response_event = threading.Event()
        self._response_data: Optional[dict] = None

    @property
    def is_connected(self) -> bool:
        return self.enabled

    @property
    def tcp_connected(self) -> bool:
        return self._tcp_connected

    def start(self) -> None:
        self._running = True
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.settimeout(1.0)
        self._server.bind((self._host, self._port))
        self._server.listen(1)
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        logger.info(f"VirtualLink TCP server on {self._host}:{self._port}")

    def stop(self) -> None:
        self._running = False
        self._subscriptions.clear()
        self._response_event.set()
        if self._client:
            try: self._client.close()
            except: pass
            self._client = None
            self._tcp_connected = False
        if self._server:
            try: self._server.close()
            except: pass
            self._server = None

    def _accept_loop(self):
        while self._running:
            try:
                client, addr = self._server.accept()
                if self._client:
                    try: self._client.close()
                    except: pass
                self._client = client
                self._client.settimeout(self._timeout)
                self._tcp_connected = True
                logger.info(f"Unity connected from {addr}")
                self._resend_subscriptions()
                self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self._listen_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    continue
                break

    def _resend_subscriptions(self):
        for sensor in list(self._subscriptions.keys()):
            try:
                self._send_message({"type": "subscribe", "sensor": sensor})
            except (OSError, BrokenPipeError):
                break

    def _listen_loop(self):
        while self._running and self._tcp_connected:
            try:
                msg = self._recv_message()
                if msg is None:
                    break
                if "result" in msg:
                    self._response_data = msg
                    self._response_event.set()
                else:
                    self._handle_push(msg)
            except (socket.timeout, ConnectionResetError, OSError):
                if not self._running:
                    break
                continue
        self._tcp_connected = False
        self._response_event.set()
        logger.info("Unity disconnected")

    def _handle_push(self, msg: dict):
        msg_type = msg.get("type")
        if msg_type == "subscription_data":
            sensor = msg.get("sensor", "")
            data = msg.get("data")
            cb = self._subscriptions.get(sensor)
            if cb and data is not None:
                try:
                    cb(data)
                except Exception as e:
                    logger.error(f"Subscription callback error ({sensor}): {e}")
        elif msg_type == "frame":
            data_b64 = msg.get("data")
            if data_b64 and self.on_frame_callback:
                try:
                    frame_bytes = base64.b64decode(data_b64)
                    self.on_frame_callback(frame_bytes)
                except Exception as e:
                    logger.error(f"Frame callback error: {e}")

    def subscribe(self, sensor: str, callback: Callable) -> bool:
        self._subscriptions[sensor] = callback
        return self._send_safe({"type": "subscribe", "sensor": sensor})

    def unsubscribe(self, sensor: str) -> None:
        self._subscriptions.pop(sensor, None)
        self._send_safe({"type": "unsubscribe", "sensor": sensor})

    def _send_safe(self, msg: dict) -> bool:
        with self._write_lock:
            if not self._client or not self._tcp_connected:
                return False
            try:
                self._send_message(msg)
                return True
            except (OSError, BrokenPipeError):
                self._tcp_connected = False
                return False

    def on_command(self, command: str, action: str, kwargs: dict) -> Optional[Any]:
        with self._command_lock:
            if not self._tcp_connected:
                return self._fallback_result(command)

            self._response_event.clear()
            self._response_data = None

            request = {
                "type": "command",
                "command": command,
                "action": action,
                "kwargs": self._serialize(kwargs)
            }

            with self._write_lock:
                try:
                    self._send_message(request)
                except (OSError, BrokenPipeError):
                    self._tcp_connected = False
                    return self._fallback_result(command)

            if self._response_event.wait(timeout=self._timeout):
                if self._response_data is not None:
                    return self._response_data.get("result")
            return self._fallback_result(command)

    @staticmethod
    def _fallback_result(command: str) -> Any:
        if command in ("motors", "servo", "ping"):
            return True
        elif command == "distance":
            return 0
        elif command == "millis":
            import time
            return int((time.time() * 1000) % 1000000)
        elif command == "gyro":
            return {"accel": (0.0, 0.0, 1.0), "gyro": (0.0, 0.0, 0.0), "temperature": 25.0}
        return True

    def _send_message(self, obj: dict):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        header = struct.pack(">I", len(data))
        self._client.sendall(header + data)

    def _recv_message(self) -> Optional[dict]:
        header = self._recv_exact(HEADER_SIZE)
        if header is None:
            return None
        length = struct.unpack(">I", header)[0]
        if length > 10_000_000:
            return None
        body = self._recv_exact(length)
        if body is None:
            return None
        return json.loads(body.decode("utf-8"))

    def _recv_exact(self, n: int) -> Optional[bytes]:
        buf = bytearray()
        while len(buf) < n:
            try:
                chunk = self._client.recv(n - len(buf))
                if not chunk:
                    return None
                buf.extend(chunk)
            except socket.timeout:
                if not self._running:
                    return None
                continue
        return bytes(buf)

    @staticmethod
    def _serialize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: VirtualLinkSubscriber._serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [VirtualLinkSubscriber._serialize(v) for v in obj]
        if isinstance(obj, bytes):
            return list(obj)
        return obj