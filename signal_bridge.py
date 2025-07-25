"""
signal_bridge.py - Unified bridge between E84 software signals and hardware I/O

This module provides bridge implementations for all operating modes:
- Production/Emulation: E84SignalBridge with real hardware interfaces
- Simulation: SimulatedE84SignalBridge without hardware dependencies
"""

from loguru import logger

from callback_manager import CallbackManager, SignalType
from signal_manager import SignalManager


class BridgeBase:
    """
    Abstract base class for E84 signal bridges.
    Defines common interface and shared functionality.
    """

    # Define which signals are outputs (we write to hardware)
    OUTPUT_SIGNALS = {'L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES'}

    # Define which signals are inputs (we read from hardware)
    INPUT_SIGNALS = {
        'CS_0',
        'CS_1',
        'VALID',
        'TR_REQ',
        'BUSY',
        'COMPT',
        'CARRIER_PRESENT_0',
        'LATCH_LOCKED_0',
        'LPT_ERROR_0',
        'LPT_READY_0',
        'CARRIER_PRESENT_1',
        'LATCH_LOCKED_1',
        'LPT_ERROR_1',
        'LPT_READY_1',
    }

    def __init__(
        self, signal_manager: SignalManager, callback_manager: CallbackManager
    ):
        """
        Initialize the base bridge.

        Args:
            signal_manager: The E84 signal manager
            callback_manager: The E84 callback manager
        """
        self.signal_manager = signal_manager
        self.callback_manager = callback_manager

        # Set of signals that have been initialized
        self.initialized_signals: set[str] = set()

    def _register_output_callbacks(self):
        """Register callbacks for all output signals"""
        for signal in self.OUTPUT_SIGNALS:
            try:
                self.signal_manager.add_watcher(
                    signal, callback=self._handle_output_signal_change
                )
                logger.debug(f'Registered callback for output signal: {signal}')

            except (KeyError, AttributeError) as e:
                logger.warning(f'Could not register callback for {signal}: {e}')

    def _handle_output_signal_change(
        self, signal: str, new_value: bool, old_value: bool
    ):
        """
        Handle changes to output signals and update hardware.
        Must be implemented by derived classes.

        Args:
            signal: The signal that changed
            old_value: Previous signal value
            new_value: New signal value
        """
        raise NotImplementedError('Derived classes must implement this method')

    def initialize(self):
        """
        Initialize the bridge by syncing all signals with hardware.
        Must be implemented by derived classes.
        """
        raise NotImplementedError('Derived classes must implement this method')

    def shutdown(self):
        """
        Shutdown the bridge and stop hardware monitoring.
        Must be implemented by derived classes.
        """
        raise NotImplementedError('Derived classes must implement this method')

    def set_output_pin(self, signal: str, value: bool):
        """Set an output pin (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def read_input_pin(self, signal: str) -> bool:
        """Read an input pin (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')


class SimulatedE84SignalBridge(BridgeBase):
    """
    Simulated bridge between E84 software signals and hardware I/O.

    This class mimics the functionality of E84SignalBridge without requiring
    hardware drivers. It's used in simulation mode.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        hardware_interface,
    ):
        """
        Initialize the simulated E84 signal bridge.

        Args:
            signal_manager: The E84 signal manager
            callback_manager: The E84 callback manager
            hardware_interface: The simulated hardware interface
        """
        super().__init__(signal_manager, callback_manager)
        self.hardware = hardware_interface

        # Register callback for all output signals
        self._register_output_callbacks()

        logger.info('Simulated E84 signal bridge initialized')

    def _handle_output_signal_change(
        self,
        signal: str,
        new_value: bool,
        old_value: bool,
    ):
        """
        Handle changes to output signals and update simulated hardware

        Args:
            signal: The signal that changed
            old_value: Previous signal value
            new_value: New signal value
        """
        if signal in self.OUTPUT_SIGNALS:
            logger.debug(
                f'Output signal {signal} changed from {old_value} to {new_value}'
            )

            # Update the simulated hardware
            self.hardware.set_output_pin(signal, new_value)

    def initialize(self):
        """Initialize the bridge by syncing all signals with simulated hardware"""
        logger.info('Initializing simulated E84 signal bridge')

        # First, read all input signals from hardware and update signal manager
        for signal in self.INPUT_SIGNALS:
            try:
                value = self.hardware.read_input_pin(signal)
                self.signal_manager.set_signal(signal, value)
                logger.debug(f'Initialized input signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize input signal {signal}: {e}')

        # Now, write all output signals to hardware
        for signal in self.OUTPUT_SIGNALS:
            try:
                value = self.signal_manager.get_signal(signal)
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Initialized output signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize output signal {signal}: {e}')

        # Start hardware input monitoring
        self.hardware.start_input_monitoring()
        logger.info(
            f'Simulated E84 signal bridge initialized with {len(self.initialized_signals)} signals'
        )

    def shutdown(self):
        """Shutdown the bridge and stop hardware monitoring"""
        logger.info('Shutting down simulated E84 signal bridge')
        self.hardware.stop_input_monitoring()

        # Set safe output states before shutdown
        safe_outputs = {
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,
            'ES': True,
        }

        for signal, value in safe_outputs.items():
            try:
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Set {signal} to safe state: {value}')
            except Exception as e:
                logger.error(f'Failed to set {signal} to safe state: {e}')

        self.hardware.close()
        logger.info('Simulated E84 signal bridge shut down')

    def set_output_pin(self, signal: str, value: bool):
        """Delegate to hardware interface"""
        return self.hardware.set_output_pin(signal, value)

    def read_input_pin(self, signal: str) -> bool:
        """Delegate to hardware interface"""
        return self.hardware.read_input_pin(signal)


class E84SignalBridge(BridgeBase):
    """
    Bridge between E84 software signals and real hardware I/O.

    This class serves as a bridge between the software signal system used by the E84 controller
    and the physical I/O pins on the DIO card. It:

    1. Monitors the signal_manager for changes to output signals
    2. Updates the physical DIO pins when output signals change
    3. Provides a clean abstraction between the E84 controller and hardware
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        hardware_interface,
    ):
        """
        Initialize the E84 signal bridge

        Args:
            signal_manager: The E84 signal manager
            callback_manager: The E84 callback manager
            hardware_interface: The DIO hardware interface
        """
        super().__init__(signal_manager, callback_manager)
        self.hardware = hardware_interface

        # Register callback for all output signals
        self._register_output_callbacks()

    def _handle_output_signal_change(
        self, signal: str, new_value: bool, old_value: bool
    ):
        """
        Handle changes to output signals and update hardware

        Args:
            signal: The signal that changed
            old_value: Previous signal value
            new_value: New signal value
        """
        if signal in self.OUTPUT_SIGNALS:
            logger.debug(
                f'Output signal {signal} changed from {old_value} to {new_value}'
            )

            # Update the physical output pin
            self.hardware.set_output_pin(signal, new_value)

    def initialize(self):
        """Initialize the bridge by syncing all signals with hardware"""
        logger.info('Initializing E84 signal bridge')

        # First, read all input signals from hardware and update signal manager
        for signal in self.INPUT_SIGNALS:
            try:
                value = self.hardware.read_input_pin(signal)
                self.signal_manager.set_signal(signal, value)
                logger.debug(f'Initialized input signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize input signal {signal}: {e}')

        # Now, write all output signals to hardware
        for signal in self.OUTPUT_SIGNALS:
            try:
                value = self.signal_manager.get_signal(signal)
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Initialized output signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize output signal {signal}: {e}')

        # Start hardware input monitoring
        self.hardware.start_input_monitoring()
        logger.info(
            f'E84 signal bridge initialized with {len(self.initialized_signals)} signals'
        )

    def shutdown(self):
        """Shutdown the bridge and stop hardware monitoring"""
        logger.info('Shutting down E84 signal bridge')
        self.hardware.stop_input_monitoring()

        # Set safe output states before shutdown
        safe_outputs = {
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,
            'ES': True,
        }

        for signal, value in safe_outputs.items():
            try:
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Set {signal} to safe state: {value}')
            except Exception as e:
                logger.error(f'Failed to set {signal} to safe state: {e}')

        self.hardware.close()
        logger.info('E84 signal bridge shut down')

    def set_output_pin(self, signal: str, value: bool):
        """Delegate to hardware interface"""
        return self.hardware.set_output_pin(signal, value)

    def read_input_pin(self, signal: str) -> bool:
        """Delegate to hardware interface"""
        return self.hardware.read_input_pin(signal)


# Factory function to create the appropriate bridge based on operating mode
def create_bridge(
    signal_manager: SignalManager,
    callback_manager: CallbackManager,
    hardware_interface,
    operating_mode: str,
) -> BridgeBase:
    """
    Create the appropriate bridge implementation based on operating mode.

    Args:
        signal_manager: Signal manager instance
        callback_manager: Callback manager instance
        hardware_interface: Hardware interface instance
        operating_mode: Operating mode (production, emulation, simulation)

    Returns:
        An appropriate bridge implementation
    """
    if operating_mode.lower() in ['simulation', 'sim']:
        logger.info('Creating Simulated signal bridge')
        return SimulatedE84SignalBridge(
            signal_manager, callback_manager, hardware_interface
        )

    else:
        logger.info('Creating Production signal bridge')
        return E84SignalBridge(signal_manager, callback_manager, hardware_interface)
