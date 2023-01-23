import json
import logging
import queue
from contextlib import asynccontextmanager
from logging.handlers import QueueHandler
from typing import Awaitable, Callable, AsyncContextManager

import trio


@asynccontextmanager
async def log_forwarder(
        handle_record: Callable[[logging.LogRecord], Awaitable[None]]
) -> AsyncContextManager[queue.SimpleQueue]:
    #
    logs = queue.SimpleQueue()
    handler = QueueHandler(logs)
    logging.root.addHandler(handler)

    async def drain_loop():
        while True:
            while not logs.empty():
                await handle_record(logs.get_nowait())
            await trio.sleep(0)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(drain_loop)
        try:
            yield logs
        finally:
            logging.root.removeHandler(handler)
            nursery.cancel_scope.cancel()


@asynccontextmanager
async def file_log_forwarder(filename: str) -> AsyncContextManager[queue.SimpleQueue]:
    async with await trio.open_file(filename, "a+") as logfile:
        async def handle_record(record: logging.LogRecord):
            await logfile.write(json.dumps(record.__dict__) + "\n")

        async with log_forwarder(handle_record) as logs:
            yield logs
