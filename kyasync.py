import os
import select
import sys
from typing import AsyncIterator

import trio


async def stdin() -> AsyncIterator[str]:
    # TODO(kamen) -- there may be better trio way to do this...
    #   this one below blocks waiting to read...
    #
    # async with trio.wrap_file(sys.stdin) as stdin:
    #     async for line in stdin:
    #         print(f"GOT: {line}")
    #
    data = b""
    while True:
        fds = select.select([sys.stdin.fileno()], [], [], 0)
        if fds[0]:
            data += os.read(sys.stdin.fileno(), 1024)

            # TODO(kamen): support less than a full line of text...
            terms = data.split(b"\n", 1)
            if len(terms) > 1:
                yield terms[0].decode("utf-8")
                data = terms[1]

        # TODO(kamen): is 0 too aggressive? can we get away with larger number?
        await trio.sleep(0)
