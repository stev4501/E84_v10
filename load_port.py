# load_port.py

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from loguru import logger

from signal_manager import SignalManager


class LPTSignals(Enum):
    """
    PIO signals from LPT2200 manual.
    *CARRIER_PRESENT: Active low when LPT is in Auto Mode and a SMIF-Pod is physically located on the LPT’s port plate. Not active Manual Mode or upon Pod removal.

    *LATCH_LOCKED: This signal is set to active whenever the LPT is powered on, in Auto mode, and the hold-down latches on the port are extended, firmly locking the SMIF-Pod onto the port plate.
        - It is set to inactive whenever the LPT is in teach mode, or the port is in an Unlock state (hold-down latches are fully retracted).
        - The PORT STATUS would remain unchanged if the port lock (or unlock) operation has failed and the hold-down latches stopped in an in-between state. In this case, the LPT would be placed in an alarm condition and the PORT STATUS is meaningless.

    *LPT_READY: Active low when LPT is in Home position and Auto Mode is enabled.
        - Not active in Manual Mode or while a cassette load or unload operation is in progress.

    *LPT_ERROR: Active whenever the LPT has encountered an abnormal abort condition during either a LOAD, UNLOAD, HOME, LOCK PORT or UNLOCK PORT operation.
    """

    CARRIER_PRESENT = auto()
    LATCH_LOCKED = auto()
    LPT_READY = auto()
    LPT_ERROR = auto()


@dataclass
class PortStatus:
    """Represents the physical state of a specific port"""

    port_id: int
    carrier_present: bool
    latch_locked: bool
    lpt_ready: bool
    error_active: bool

    @property
    def is_ready_for_load(self) -> bool:
        return (
            not self.carrier_present
            and not self.latch_locked
            and not self.error_active
            and self.lpt_ready
        )

    @property
    def is_ready_for_unload(self) -> bool:
        return (
            self.carrier_present
            and not self.latch_locked
            and not self.error_active
            and self.lpt_ready
        )

    def __str__(self) -> str:
        return (
            f'LPT_{self.port_id} | '
            f'Carrier: {"Present" if self.carrier_present else "Not Present"} | '
            f'Latch: {"Locked" if self.latch_locked else "Unlocked"} | '
            f'Error: {"Active" if self.error_active else "None"} | '
            f'LPT Ready: {"Yes" if self.lpt_ready else "No"}'
        )


class LoadPort:
    """Manages load port hardware status and operations"""

    def __init__(
        self, port_id: int, signal_manager: SignalManager, operating_mode: str = 'prod'
    ):
        self.port_id = port_id
        self.signal_manager = signal_manager
        self.operating_mode = operating_mode
        self.status_record = []

        # Initialize internal hardware signal states
        self._signals: dict[LPTSignals, bool] = {
            LPTSignals.CARRIER_PRESENT: False,
            LPTSignals.LATCH_LOCKED: False,
            LPTSignals.LPT_READY: True,
            LPTSignals.LPT_ERROR: False,
        }

        # Callback for LPT_READY changes
        self._on_lpt_ready_changed: Callable[[int, bool], None] | None = None
        self._on_carrier_changed: Callable[[int, bool], None] | None = None

    @property
    def unload_ready(self) -> bool:
        if self.operating_mode == 'em':
            return True
        if self.operating_mode == 'prod':
            return self.get_port_status().is_ready_for_unload

    @property
    def load_ready(self) -> bool:
        if self.operating_mode == 'em':
            return True
        if self.operating_mode == 'prod':
            return self.get_port_status().is_ready_for_load

    @property
    def ready_and_error_clear(self) -> bool:
        if self.operating_mode == 'em':
            return True
        if self.operating_mode in ('prod', 'sim'):
            port_status = self.get_port_status()
            return port_status.lpt_ready and not port_status.error_active

        else:
            logger.warning(f'Invalid operating mode error: {self.operating_mode}')
            port_status = self.get_port_status()
            return port_status.lpt_ready and not port_status.error_active

    def __str__(self) -> str:
        return f'LPT_{self.port_id}'

    def register_lpt_ready_callback(
        self, callback: Callable[[int, bool], None]
    ) -> None:
        """Register a callback for LPT_READY signal changes"""
        self._on_lpt_ready_changed = callback

    def register_carrier_callback(self, callback: Callable[[int, bool], None]) -> None:
        """Register a callback for CARRIER_PRESENT signal changes"""
        self._on_carrier_changed = callback

    def get_port_status(self) -> PortStatus:
        """Get current state of this port"""
        return PortStatus(
            port_id=self.port_id,
            carrier_present=self.signal_manager.get_signal(
                f'CARRIER_PRESENT_{self.port_id}'
            ),
            latch_locked=self.signal_manager.get_signal(f'LATCH_LOCKED_{self.port_id}'),
            lpt_ready=self.signal_manager.get_signal(f'LPT_READY_{self.port_id}'),
            error_active=self.signal_manager.get_signal(f'LPT_ERROR_{self.port_id}'),
        )

    def get_port_status_record(self) -> list[dict[str, str]]:
        """
        Returns a list of dictionaries containing signal names and their current values.
        """
        signal_map = {
            'carrier_present': f'CARRIER_PRESENT_{self.port_id}',
            'latch_locked': f'LATCH_LOCKED_{self.port_id}',
            'lpt_ready': f'LPT_READY_{self.port_id}',
            'error_active': f'LPT_ERROR_{self.port_id}',
        }
        signals = [
            {
                'signal': signal_map['carrier_present'],
                'value': self.get_signal(LPTSignals.CARRIER_PRESENT),
            },
            {
                'signal': signal_map['latch_locked'],
                'value': self.get_signal(LPTSignals.LATCH_LOCKED),
            },
            {
                'signal': signal_map['lpt_ready'],
                'value': self.get_signal(LPTSignals.LPT_READY),
            },
            {
                'signal': signal_map['error_active'],
                'value': self.get_signal(LPTSignals.LPT_ERROR),
            },
        ]
        return signals

    def set_signal(self, signal: LPTSignals, new_value: bool) -> None:
        signal_map = {
            LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
            LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
            LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
            LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
        }
        old_value: bool = self._signals[signal]

        if old_value == new_value:
            return

        self._signals[signal] = new_value

        self.signal_manager.set_signal(signal_map[signal], new_value)

    def get_signal(self, signal: LPTSignals) -> bool:
        signal_map = {
            LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
            LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
            LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
            LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
        }
        return self.signal_manager.get_signal(signal_map[signal])

    def is_ho_avbl(self) -> bool:
        """
        Check if port is available for handoff operations,
        this will set HO_AVBL signal when port is selected.
        Also, validates if conditions are correct to start the handshake.
        """
        if self.operating_mode == 'em':
            return True
        if self.operating_mode == 'prod':
            return self.signal_manager.get_signal(
                f'LPT_READY_{self.port_id}'
            ) and not self.signal_manager.get_signal(f'LPT_ERROR_{self.port_id}')

    def reset(self) -> None:
        """
        For simulation purposes,
        Reset port to default state
        """
        self._signals: dict[LPTSignals, bool] = {
            LPTSignals.CARRIER_PRESENT: False,
            LPTSignals.LATCH_LOCKED: False,
            LPTSignals.LPT_READY: True,
            LPTSignals.LPT_ERROR: False,
        }
        logger.debug(f'Port {self.port_id} reset to default state')
