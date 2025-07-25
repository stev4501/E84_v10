# signal_manager.py

import inspect
import os
from collections.abc import Callable

from loguru import logger

from callback_manager import CallbackManager, SignalType


class SignalManager:
    """
    This function initializes the SignalManager object by setting the initial values of the signals.
    The signals are stored in a dictionary called 'signals' and can have multiple callbacks.
    """

    def __init__(self) -> None:
        self.callback_manager = CallbackManager()

        self.signals = {
            # AGV (Active Equipment) Signals
            'CS_0': False,
            'CS_1': False,
            'VALID': False,
            'TR_REQ': False,
            'BUSY': False,
            'COMPT': False,
            # E84 Controller (Passive Equipment) Signals
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,  # Default to True per spec
            'ES': True,  # Default to True per spec
            ## Load Port Specific Signals
            # Port 0
            'CARRIER_PRESENT_0': False,
            'LATCH_LOCKED_0': False,
            'LPT_ERROR_0': False,
            'LPT_READY_0': True,
            # Port 1
            'CARRIER_PRESENT_1': False,
            'LATCH_LOCKED_1': False,
            'LPT_ERROR_1': False,
            'LPT_READY_1': True,
            # Mainframe Signal
            # "TOOL_EMO": False,
        }

        self.watchers: dict[str, list[Callable[[bool, bool], None]]] = {}

        self.initialize_signals()

    def initialize_signals(self) -> None:
        """
        Set the initial values of the signals.

        Raises:
            ValueError: If any signal does not exist in the signal dictionary.
        """
        for signal in self.signals:
            if signal not in self.signals:
                raise ValueError(f'Signal {signal} does not exist.')
            self.set_signal(signal, self.signals[signal])
        return self.signals

    def add_watcher(self, signal_name: str, callback: Callable) -> None:
        """Register a callback for a signal"""
        try:
            signal_type = SignalType[signal_name]

            self.callback_manager.register(
                signal_type=signal_type,
                callback=callback,
            )
            self.watchers.setdefault(signal_name, []).append(callback)

        except KeyError:
            logger.error(f'Invalid signal name: {signal_name}')

    def remove_watcher(self, signal_name: str, callback: Callable) -> None:
        """Remove a callback for a signal"""
        try:
            signal_type = SignalType[signal_name]
            source = os.path.basename(inspect.getsourcefile(callback))
            dest = os.path.basename(inspect.stack()[1].filename)

            self.callback_manager.remove(
                signal_type=signal_type, source=source, dest=dest
            )
            self.watchers[signal_name].remove(callback)

        except KeyError:
            logger.error(f'Invalid signal name: {signal_name}')

    def set_signal(self, signal_name: str, new_value: bool) -> None:
        """Set signal value and notify watchers"""
        if signal_name not in self.signals:
            raise ValueError(f'Invalid signal: {signal_name}')

        old_value = self.signals.get(signal_name)
        if old_value != new_value:
            self.signals[signal_name] = new_value
            logger.info(f'Signal {signal_name} changed: {old_value} -> {new_value}')

            try:
                if signal_name in SignalType.__members__:
                    signal_type = SignalType[signal_name]
                    self.callback_manager.notify(signal_type, new_value, old_value)
            except KeyError:
                pass

    def get_signal(self, signal_name: str) -> bool:
        """Get current signal value."""
        if signal_name not in self.signals:
            logger.error(f'Attempted to get unknown signal: {signal_name}')
            return False

        return self.signals[signal_name]

    def signal_snapshot(self) -> list[tuple[str, bool]]:
        """
        Returns a list of the self.signals dictionary items
        """
        sig_dict = {signal: value for signal, value in self.signals.items()}
        sig_list = list(sig_dict.items())

        return sig_list

    def reset_signal_manager(self) -> None:
        """Reset all signals to their initial states."""
        try:
            # Initialize with default values
            defaults: dict[str, bool] = {
                # AGV (Active Equipment) Signals
                'CS_0': False,
                'CS_1': False,
                'VALID': False,
                'TR_REQ': False,
                'BUSY': False,
                'COMPT': False,
                # E84 Controller (Passive Equipment) Signals
                'L_REQ': False,
                'U_REQ': False,
                'READY': False,
                'HO_AVBL': True,
                'ES': True,
                ## Load Port Specific Signals
                # Port 0
                'CARRIER_PRESENT_0': False,
                'LATCH_LOCKED_0': False,
                'LPT_ERROR_0': False,
                'LPT_READY_0': True,
                # Port 1
                'CARRIER_PRESENT_1': False,
                'LATCH_LOCKED_1': False,
                'LPT_ERROR_1': False,
                'LPT_READY_1': True,
            }

            # Reset all signals to their default values
            for sig, val in defaults.items():
                self.set_signal(sig, val)
            logger.debug('All Signal Manager signals reset to default values')

        except Exception as e:
            logger.error(f'Error resetting all signals: {str(e)}')

    def reset_passive_signals(self):
        try:
            # Initialize with default values
            defaults: dict[str, bool] = {
                'L_REQ': False,
                'U_REQ': False,
                'READY': False,
                'HO_AVBL': True,
                'ES': True,
            }

            # Reset passive signals to their default values
            for sig, val in defaults.items():
                self.set_signal(sig, val)
            logger.debug('All Signal Manager passive signals reset to default values')

        except Exception as e:
            logger.error(f'Error resetting passive signals: {str(e)}')
