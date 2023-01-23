import logging
from typing import Callable, Awaitable

import trio
from trio import Nursery

from kybeat_client import KyBeatClient
from kybeat_status import KyBeatStatus


class KyBeatWatcher:
    def __init__(self, *,
                 interrupter: Callable[[], Awaitable[None]] | None = None,
                 terminator: Callable[[], Awaitable[None]] | None = None):
        self._logger = logging.getLogger("KyBeatWatcher")
        self._interrupting = False
        self._interrupter = interrupter
        self._terminating = False
        self._terminator = terminator

    async def loop(self, beat: KyBeatClient, nursery: Nursery):
        while True:
            # TODO(kamen): catch when connection is broken and nuke!
            await beat.send(ping="hi!")

            if not self._interrupting and beat.get_status() == KyBeatStatus.INTERRUPT:
                self._interrupting = True
                nursery.start_soon(self._handle_interrupt)

            if not self._terminating and beat.get_status() == KyBeatStatus.TERMINATE:
                self._terminating = True
                nursery.start_soon(self._handle_terminate)

            # back off a bit so that we don't storm the server!
            await trio.sleep(0.25)

    async def _handle_interrupt(self):
        if self._interrupter:
            await self._interrupter()

    async def _handle_terminate(self):
        # TODO(kamen): do we need a default terminator that kills itself and its process tree?
        if self._terminator:
            await self._terminator()
