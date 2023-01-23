import json
import logging

import trio

_logger = logging.getLogger("message")


async def _read_n(stream: trio.abc.Stream, n: int) -> bytes:
    data = b""
    while len(data) < n:
        data += await stream.receive_some(n - len(data))
    return data


async def read(stream: trio.abc.Stream) -> dict[str, any]:
    size = int.from_bytes(await _read_n(stream, 4), "little")
    data = await _read_n(stream, size)
    text = data.decode("utf-8")
    message = json.loads(text)
    _logger.debug("RX", extra={"kybeat": False, "msg_rx": message})
    return message


async def write(stream: trio.abc.Stream, message: dict[str, any]):
    text = json.dumps(message, default=str)
    data = text.encode("utf-8")
    size = len(data)
    await stream.send_all(size.to_bytes(4, "little"))
    await stream.send_all(data)
    _logger.debug("TX", extra={"kybeat": False, "msg_tx": message})
