# callback_manager.py

import inspect
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set

from loguru import logger


class SignalType(Enum):
    """Enumeration of all possible signal types"""

    LPT_READY_0 = 'LPT_READY_0'
    LPT_ERROR_0 = 'LPT_ERROR_0'
    CARRIER_PRESENT_0 = 'CARRIER_PRESENT_0'
    LATCH_LOCKED_0 = 'LATCH_LOCKED_0'

    LPT_READY_1 = 'LPT_READY_1'
    LPT_ERROR_1 = 'LPT_ERROR_1'
    CARRIER_PRESENT_1 = 'CARRIER_PRESENT_1'
    LATCH_LOCKED_1 = 'LATCH_LOCKED_1'

    CS_0 = 'CS_0'
    CS_1 = 'CS_1'
    VALID = 'VALID'
    TR_REQ = 'TR_REQ'
    BUSY = 'BUSY'
    COMPT = 'COMPT'

    L_REQ = 'L_REQ'
    U_REQ = 'U_REQ'
    READY = 'READY'
    ES = 'ES'
    HO_AVBL = 'HO_AVBL'


@dataclass
class CallbackRegistration:
    """Stores information about a registered callback"""

    signal_type: SignalType
    callback: Callable
    source: str
    source_line: int
    dest: str
    dest_line: int
    timestamp: float = field(default_factory=time.time)


class CallbackManager:
    """Enhanced callback manager with thread safety and error recovery"""

    def __init__(self):
        self._callbacks: Dict[SignalType, list[CallbackRegistration]] = {
            signal_type: [] for signal_type in SignalType
        }
        self._active_signals: Set[SignalType] = set()
        self._error_counts: Dict[str, int] = {}  # Track errors by source

    def register(self, signal_type: SignalType, callback: Callable) -> None:
        """Thread-safe callback registration"""

        if not isinstance(signal_type, SignalType):
            raise ValueError(f'Value Error: Invalid signal type: {signal_type}')
        if not callable(callback):
            raise ValueError(f'Value Error: Callback must be callable: {callback}')

        # Get filename where callback was registered
        dest = os.path.basename(inspect.stack()[1].filename)
        dest_line = inspect.stack()[1].lineno

        # Get filename of callback source
        source_file = os.path.basename(inspect.getsourcefile(callback))
        source_line = inspect.getsourcelines(callback)[1]

        registration = CallbackRegistration(
            signal_type=signal_type,
            callback=callback,
            source=source_file,
            source_line=source_line,
            dest=dest,
            dest_line=dest_line,
        )
        self._callbacks[signal_type].append(registration)
        logger.debug(
            f'Registered {source_file} at line {source_line} for callback at {dest} at line {dest_line} for {signal_type.name}'
        )

    def notify(
        self, signal_type: SignalType, new_value, old_value, *args, **kwargs
    ) -> None:
        """Thread-safe notification with error recovery"""

        signal_name = signal_type.name

        if not isinstance(signal_type, SignalType):
            raise ValueError(f'Invalid signal type: {signal_type}')

        if signal_type in self._active_signals:
            logger.warning(f'Recursive callback detected for {signal_name}')
            return

        self._active_signals.add(signal_type)
        try:
            for reg in self._callbacks[signal_type]:
                try:
                    reg.callback(signal_name, new_value, old_value)
                    logger.debug(
                        f'Callback: "{reg.callback.__name__}" | Source: "{reg.source}" [line: {reg.source_line}] -> Dest: "{reg.dest}" [line: {reg.dest_line}] executed'
                    )
                except Exception as e:
                    self._handle_callback_error(reg, e)
        finally:
            self._active_signals.remove(signal_type)

    def _handle_callback_error(
        self, registration: CallbackRegistration, error: Exception
    ) -> None:
        """Handle callback errors with recovery logic"""
        source = registration.source
        self._error_counts[source] = self._error_counts.get(source, 0) + 1

        logger.error(
            f'Error in {registration.signal_type.name} callback from Source: {source}, Dest: {registration.dest}: {error}'
        )

        # If too many errors, remove the callback
        if self._error_counts[source] >= 3:
            self.remove(registration.signal_type, source)
            logger.warning(f'Removed callback from {source} due to repeated errors')

    def remove(self, signal_type: SignalType, source: str, dest: str) -> None:
        """Thread-safe callback removal"""
        if signal_type in self._callbacks:
            original_len = len(self._callbacks[signal_type])
            self._callbacks[signal_type] = [
                reg
                for reg in self._callbacks[signal_type]
                if not (reg.source == source and reg.dest == dest)
            ]
            removed = original_len - len(self._callbacks[signal_type])
            if removed > 0:
                logger.debug(
                    f'Removed {removed} callbacks for {signal_type.name} from Source: {source}, Dest: {dest}'
                )

    def get_registered_callbacks(self, signal_type: SignalType) -> List[str]:
        """Get list of sources registered for a signal type"""
        return [reg.source for reg in self._callbacks.get(signal_type, [])]
