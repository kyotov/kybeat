import logging
import os
import socket
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import trio.abc

import log_forwarder
import message
from kybeat_status import KyBeatStatus


class KyBeatClient:
    def __init__(self, addr: str):
        self._parent_uuid, self._server_addr, server_port = addr.split('!')
        self._server_port = int(server_port)

        self._uuid = str(uuid.uuid4())
        self._host = socket.gethostname()
        self._pid = os.getpid()

        self._stream: trio.abc.Stream | None = None
        self._lock = trio.Lock()
        self._status = KyBeatStatus.OK

        self._logger = logging.getLogger("KyBeat_Client")

    def get_status(self) -> KyBeatStatus:
        return self._status

    async def send(self, **kwargs):
        await self._send(self._message("custom", **kwargs))

    @asynccontextmanager
    async def context(self):
        async with log_forwarder.log_forwarder(self._handle_log_record):
            try:
                await self._connect()
                await self._send(self._message("hello", parent=self._parent_uuid, host=self._host, pid=self._pid))
                yield self
            finally:
                await self._send(self._message("goodbye"))

    async def _connect(self):
        try:
            self._stream = await trio.open_tcp_stream(self._server_addr, self._server_port)
            self._logger.debug(f"connected to kybeat server at [{self._server_addr}]:{self._server_port}",
                               extra={"kybeat": False})
        except OSError as e:
            self._logger.warning(
                f"failed to connect to kybeat server at [{self._server_addr}]:{self._server_port}; "
                "kybeat will be disabled! (%s)",
                e,
                extra={"kybeat": False})

    async def _send(self, value: dict[str, any]):
        if self._stream:
            async with self._lock:
                await message.write(self._stream, value)
                response = await message.read(self._stream)
                self._status = KyBeatStatus(response.get("status"))

    def _message(self, _type: str, **kwargs) -> dict[str, any]:
        return {
            "ts": datetime.now().isoformat(),
            "uuid": self._uuid,
            "type": _type,
            **kwargs
        }

    async def _handle_log_record(self, record: logging.LogRecord):
        if record.__dict__.get("kybeat", True):
            await self._send(self._message("log", **record.__dict__))
