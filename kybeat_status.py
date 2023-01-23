from enum import Enum


class KyBeatStatus(Enum):
    OK = "ok"
    INTERRUPT = "interrupt"
    TERMINATE = "terminate"
    KILL = "kill"
