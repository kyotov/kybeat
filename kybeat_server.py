import logging
import queue
import signal
import subprocess
import sys
import uuid
from functools import partial

import trio
from trio import Nursery, Process

import kyasync
import log_forwarder
import message
from kybeat_status import KyBeatStatus


class KyBeatServer:
    def __init__(self, command: str):
        self._uuid = str(uuid.uuid4())

        self._command = command
        self._status = KyBeatStatus.OK
        self._return_code = 0

        self._logger = logging.getLogger("KyBeatServer")
        self._logs: queue.SimpleQueue | None = None

        trio.run(self.run)

    async def run(self):
        async with log_forwarder.file_log_forwarder("beat.log") as self._logs:
            with trio.open_signal_receiver(signal.SIGINT) as signals:
                async with trio.open_nursery() as nursery:
                    listeners = await nursery.start(trio.serve_tcp, self._handle_child_messages, 0)
                    host, port = listeners[0].socket.getsockname()[0:2]
                    self._logger.info(f"started listening on [{host}]:{port}")
                    nursery.start_soon(self._handle_signals, signals)
                    nursery.start_soon(self._run_child, nursery,
                                       f"{self._command} --beat-server={self._uuid}!{host}!{port}")

        exit(self._return_code)

    async def _handle_child_messages(self, stream: trio.abc.Stream):
        while True:
            value = await message.read(stream)
            await message.write(stream, {"status": self._status.value})

            # this is so that it makes it to the trace...
            # if we wanted to do other things with the messages, we need to add further intercept here
            if self._logs:
                self._logs.put(logging.makeLogRecord(value))

            # children generally maintain a persistent connection with the server;
            # they send `goodbye` when done
            if value.get("type") == "goodbye":
                return

    async def _handle_signals(self, signals):
        async for signum in signals:
            assert signum == signal.SIGINT

            self._status = {
                KyBeatStatus.OK: KyBeatStatus.INTERRUPT,
                KyBeatStatus.INTERRUPT: KyBeatStatus.TERMINATE,
                KyBeatStatus.TERMINATE: KyBeatStatus.KILL,
            }[self._status]

            logging.info("MODE: %s", self._status)

            if self._status == KyBeatStatus.KILL:
                logging.warning("killing...")
                exit(3)

    async def _run_child(self, nursery: Nursery, command: str):
        p = partial(trio.run_process, command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=True, start_new_session=True, check=False)
        process: Process = await nursery.start(p)

        async def process_input(stream: trio.abc.Stream):
            async for line in kyasync.stdin():
                await stream.send_all((line + "\n").encode("utf-8"))

        async def process_output(stream: trio.abc.Stream):
            while data := await stream.receive_some():
                sys.stdout.write(data.decode("utf-8"))

        async def process_error(stream: trio.abc.Stream):
            while data := await stream.receive_some():
                sys.stderr.write(data.decode("utf-8"))

        nursery.start_soon(process_input, process.stdin)
        nursery.start_soon(process_output, process.stdout)
        nursery.start_soon(process_error, process.stderr)

        self._return_code = await process.wait()
        self._logger.info(f"command `{command}` finished with code {self._return_code}")
        nursery.cancel_scope.cancel()
