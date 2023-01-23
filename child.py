#!/Users/kamen/PycharmProjects/kybeat/venv/bin/python

import logging

import click
import trio
from trio import Nursery

import kyasync
from kybeat_client import KyBeatClient
from kybeat_watcher import KyBeatWatcher


class Child:
    def __init__(self, behavior: str, beat_server: str):
        self._logger = logging.getLogger("Child")
        self._beat: KyBeatClient | None = None
        self._nursery: Nursery | None = None
        self._behavior = behavior
        self._return_code = 0
        trio.run(self._run, beat_server)

    async def _waste_time(self):
        for i in range(10):
            await trio.sleep(1)

    async def _interrupt(self):
        if self._behavior == "bad":
            self._logger.info("user interrupt request detected, but the child is ignoring it...")
        else:
            self._logger.info("user interrupt request detected")

            if self._behavior == "distracted":
                self._logger.info("... but child is distracted for 2 seconds")
                await trio.sleep(2)
            else:
                assert self._behavior == "good"

            self._return_code = 2
            self._nursery.cancel_scope.cancel()

    async def _terminate(self):
        self._logger.warning("user termination request detected")
        # TODO(kamen): kill its process tree?
        exit(3)

    async def _parrot(self):
        async for line in kyasync.stdin():
            logging.info(f"GOT: {line}")

    async def _run(self, addr: str):
        async with KyBeatClient(addr).context() as self._beat:
            async with trio.open_nursery() as self._nursery:
                watcher = KyBeatWatcher(interrupter=self._interrupt, terminator=self._terminate)
                self._nursery.start_soon(watcher.loop, self._beat, self._nursery)
                self._nursery.start_soon(self._waste_time)
                self._nursery.start_soon(self._parrot)

        exit(self._return_code)


@click.command()
@click.option("--behavior", type=click.Choice(["good", "distracted", "bad"]), default="good")
@click.option("--beat-server", type=click.STRING, default="localhost:0")
def main(behavior: str, beat_server: str):
    logging.basicConfig(level=logging.INFO,
                        format=f"%(asctime)s : %(process)d ({behavior}_child:%(name)s) : [%(levelname)s] %(message)s")
    Child(behavior, beat_server)


if __name__ == "__main__":
    main()
