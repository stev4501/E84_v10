# constants.py

from collections import namedtuple
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum, auto


class TIMEOUTS(IntEnum):
    TP1 = 2
    TP2 = 2
    TP3 = 60
    TP4 = 60
    TP5 = 2


class SignalType(StrEnum):
    E84_PASSIVE = auto()
    E84_ACTIVE = auto()
    LPT = auto()
    EMO = auto()


class PassiveSignals(StrEnum):
    L_REQ = 'L_REQ'
    U_REQ = 'U_REQ'
    READY = 'READY'
    HO_AVBL = 'HO_AVBL'
    ES = 'ES'


class ActiveSignals(StrEnum):
    CS_0 = 'CS_0'
    CS_1 = 'CS_1'
    VALID = 'VALID'
    TR_REQ = 'TR_REQ'
    BUSY = 'BUSY'
    COMPT = 'COMPT'


class LoadPortSignals(Enum):
    READY = ('READY', 0, 1)
    ERROR = ('ERROR', 0, 1)
    POD_PRESENT = ('POD_PRESENT', 0, 1)
    LATCH_LOCKED = ('LATCH_LOCKED', 0, 1)

    def __init__(self, name, port_0, port_1):
        self._name_ = name
        self.port_0 = port_0
        self.port_1 = port_1


class E84States(StrEnum):
    IDLE = auto()
    HANDSHAKE_INITIATED = auto()
    TR_REQ_ON = auto()
    TRANSFER_READY = auto()
    BUSY = auto()
    CARRIER_DETECTED = auto()
    TRANSFER_COMPLETED = auto()


class UnavailableStates(StrEnum):
    IDLE_UNAVBL = auto()
    HO_UNAVBL = auto()
    ERROR_HANDLING = auto()
    ERROR_RECOVERY = auto()
    RESET = auto()


@dataclass
class BaseE84Signal:
    """Base class for managing individual E84 Signals"""

    name: str
    state: bool
    signal_type: SignalType


TimerInfo = namedtuple('TimerInfo', ['name', 'duration', 'message'])

TP1 = TimerInfo(
    name='TP1',
    duration=2.0,
    message=f'TP1 Timeout – TR_REQ signal did not turn ON within specified time. (TP1 = {TIMEOUTS.TP1.value}s)',
)
TP2 = TimerInfo(
    name='TP2',
    duration=2.0,
    message=f'TP2 Timeout – BUSY signal did not turn ON within specified time. (TP2 = {TIMEOUTS.TP2.value}s)',
)

TP3 = TimerInfo(
    name='TP3',
    duration=60,
    message=f'TP3 Timeout – Carrier not detected/removed within specified time. (TP3 = {TIMEOUTS.TP3.value}s)',
)


TP4 = TimerInfo(
    name='TP4',
    duration=60,
    message=f'TP4 Timeout – BUSY signal did not turn OFF within specified time. (TP4 = {TIMEOUTS.TP4.value}s)',
)

TP5 = TimerInfo(
    name='TP5',
    duration=2.0,
    message=f'TP5 Timeout – VALID signal did not turn OFF within specified time. (TP5 = {TIMEOUTS.TP5.value}s)',
)


# TP6 = TimerInfo(
#     name="TP6",
#     duration=2.0,
#     message=f"TP6 Timeout – VALID signal did not turn ON within specified time. (TP6 = {TIMEOUTS.TP6.value}s",
# )
